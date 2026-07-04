"""Payment checkout, status, and provider callback routes."""

from datetime import datetime  # fcg-rewrite
from typing import Optional  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import APIRouter, Depends, Header, HTTPException, Request  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite
from sqlalchemy import and_, text  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db  # fcg-rewrite
from database.models import (  # fcg-rewrite
    PackagePurchase,  # fcg-rewrite
    PaymentOrder,  # fcg-rewrite
    SubscriptionPayment,  # fcg-rewrite
    Tenant,
    TenantSubscription,  # fcg-rewrite
)
from services.alipay_service import alipay_service  # fcg-rewrite
from services.billing_service import billing_service  # fcg-rewrite
from services.payment_service import payment_service  # fcg-rewrite
from services.stripe_service import stripe_service  # fcg-rewrite
from utils.auth import verify_token  # fcg-rewrite
from utils.logger import get_logger  # fcg-rewrite

logger = get_logger(__name__)  # fcg-rewrite
router = APIRouter(prefix="/api/v1/payment", tags=["Payment"])  # fcg-rewrite


def _tenant_by_id(db: Session, tenant_id: object) -> Optional[Tenant]:  # fcg-rewrite
    try:
        tenant_uuid = uuid.UUID(str(tenant_id))  # fcg-rewrite
    except (ValueError, AttributeError, TypeError):  # fcg-rewrite
        return None  # fcg-rewrite
    return db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite


def get_current_user(request: Request, db: Session) -> Tenant:  # fcg-rewrite
    """Resolve middleware context first and bearer-token identity second."""
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if context:  # fcg-rewrite
        tenant = _tenant_by_id(db, context["data"].get("tenant_id"))  # fcg-rewrite
        if tenant:  # fcg-rewrite
            return tenant  # fcg-rewrite

    authorization = request.headers.get("Authorization", "")  # fcg-rewrite
    if not authorization.startswith("Bearer "):  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite
    try:
        email = verify_token(authorization.removeprefix("Bearer ")).get("sub")  # fcg-rewrite
        if not email:  # fcg-rewrite
            raise ValueError("Token does not identify a tenant")  # fcg-rewrite
        tenant = db.query(Tenant).filter(Tenant.email == email).first()  # fcg-rewrite
        if not tenant:  # fcg-rewrite
            raise ValueError("Tenant not found")  # fcg-rewrite
        if not tenant.is_active or not tenant.is_verified:  # fcg-rewrite
            raise PermissionError("Tenant account not active")  # fcg-rewrite
        return tenant  # fcg-rewrite
    except PermissionError as exc:  # fcg-rewrite
        raise HTTPException(status_code=403, detail=str(exc)) from exc  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("Token verification failed: %s", exc)  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Invalid token") from exc  # fcg-rewrite


class CreateSubscriptionPaymentRequest(BaseModel):  # fcg-rewrite
    tier_number: Optional[int] = None  # fcg-rewrite


class CreateQuotaPurchaseRequest(BaseModel):  # fcg-rewrite
    units: int  # fcg-rewrite


class CreatePackagePaymentRequest(BaseModel):  # fcg-rewrite
    package_id: str  # fcg-rewrite


class PaymentResponse(BaseModel):  # fcg-rewrite
    success: bool  # fcg-rewrite
    payment_id: Optional[str] = None  # fcg-rewrite
    order_id: Optional[str] = None  # fcg-rewrite
    provider: Optional[str] = None  # fcg-rewrite
    payment_url: Optional[str] = None  # fcg-rewrite
    checkout_url: Optional[str] = None  # fcg-rewrite
    session_id: Optional[str] = None  # fcg-rewrite
    amount: Optional[float] = None  # fcg-rewrite
    currency: Optional[str] = None  # fcg-rewrite
    error: Optional[str] = None  # fcg-rewrite


class SubscriptionTierResponse(BaseModel):  # fcg-rewrite
    tier_number: int  # fcg-rewrite
    tier_name: str  # fcg-rewrite
    monthly_quota: int  # fcg-rewrite
    price: float  # fcg-rewrite
    display_order: int  # fcg-rewrite


class PaymentConfigResponse(BaseModel):  # fcg-rewrite
    provider: str  # fcg-rewrite
    currency: str  # fcg-rewrite
    subscription_price: float  # fcg-rewrite
    stripe_publishable_key: Optional[str] = None  # fcg-rewrite
    tiers: list = Field(default_factory=list)  # fcg-rewrite


def _payment_error(exc: ValueError) -> PaymentResponse:  # fcg-rewrite
    return PaymentResponse(success=False, error=str(exc))  # fcg-rewrite


def _raise_payment_failure(label: str, exc: Exception) -> None:  # fcg-rewrite
    logger.error("%s error: %s", label, exc)  # fcg-rewrite
    raise HTTPException(status_code=500, detail=f"Payment creation failed: {exc}") from exc  # fcg-rewrite


@router.get("/config")  # fcg-rewrite
async def get_payment_config(db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return payment_service.get_payment_config(db=db)  # fcg-rewrite


@router.get("/tiers")  # fcg-rewrite
async def get_subscription_tiers(db: Session = Depends(get_admin_db)):  # fcg-rewrite
    provider = payment_service.get_payment_provider()  # fcg-rewrite
    price_key = "price_cny" if provider == "alipay" else "price_usd"  # fcg-rewrite
    tiers = [  # fcg-rewrite
        {
            "tier_number": tier["tier_number"],  # fcg-rewrite
            "tier_name": tier["tier_name"],  # fcg-rewrite
            "monthly_quota": tier["monthly_quota"],  # fcg-rewrite
            "price": tier[price_key],  # fcg-rewrite
            "display_order": tier["display_order"],  # fcg-rewrite
        }
        for tier in billing_service.get_all_tiers(db)  # fcg-rewrite
    ]
    return {"tiers": tiers, "currency": payment_service.get_currency()}  # fcg-rewrite


@router.post("/subscription/create", response_model=PaymentResponse)  # fcg-rewrite
async def create_subscription_payment(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    payment_request: CreateSubscriptionPaymentRequest = None,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        tenant = get_current_user(request, db)  # fcg-rewrite
        tier_number = payment_request.tier_number if payment_request else None  # fcg-rewrite
        subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
            TenantSubscription.tenant_id == tenant.id  # fcg-rewrite
        ).first()  # fcg-rewrite
        if subscription and subscription.subscription_type == "subscribed" and tier_number is None:  # fcg-rewrite
            return PaymentResponse(success=False, error="Already subscribed")  # fcg-rewrite
        result = await payment_service.create_subscription_payment(  # fcg-rewrite
            db=db, tenant_id=str(tenant.id), email=tenant.email, tier_number=tier_number  # fcg-rewrite
        )
        return PaymentResponse(**result)  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        return _payment_error(exc)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _raise_payment_failure("Subscription payment creation", exc)  # fcg-rewrite


@router.post("/package/create", response_model=PaymentResponse)  # fcg-rewrite
async def create_package_payment(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    payment_request: CreatePackagePaymentRequest,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        tenant = get_current_user(request, db)  # fcg-rewrite
        result = await payment_service.create_package_payment(  # fcg-rewrite
            db=db,
            tenant_id=str(tenant.id),  # fcg-rewrite
            email=tenant.email,  # fcg-rewrite
            package_id=payment_request.package_id,  # fcg-rewrite
        )
        return PaymentResponse(**result)  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        return _payment_error(exc)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _raise_payment_failure("Package payment creation", exc)  # fcg-rewrite


@router.post("/quota/create", response_model=PaymentResponse)  # fcg-rewrite
async def create_quota_purchase_payment(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    payment_request: CreateQuotaPurchaseRequest,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        tenant = get_current_user(request, db)  # fcg-rewrite
        if payment_request.units < 1:  # fcg-rewrite
            return PaymentResponse(success=False, error="Minimum purchase is 1 unit")  # fcg-rewrite
        result = await payment_service.create_quota_purchase_payment(  # fcg-rewrite
            db=db, tenant_id=str(tenant.id), email=tenant.email, units=payment_request.units  # fcg-rewrite
        )
        return PaymentResponse(**result)  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        return _payment_error(exc)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _raise_payment_failure("Quota purchase creation", exc)  # fcg-rewrite


@router.post("/subscription/cancel")  # fcg-rewrite
async def cancel_subscription(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        tenant = get_current_user(request, db)  # fcg-rewrite
        result = await payment_service.cancel_subscription(db=db, tenant_id=str(tenant.id))  # fcg-rewrite
        if not result.get("success"):  # fcg-rewrite
            raise HTTPException(status_code=400, detail=result.get("error", "Cancellation failed"))  # fcg-rewrite
        return result  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        logger.error("Subscription cancellation error: %s", exc)  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Cancellation failed") from exc  # fcg-rewrite


@router.get("/orders")  # fcg-rewrite
async def get_payment_orders(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    order_type: Optional[str] = None,  # fcg-rewrite
    status: Optional[str] = None,  # fcg-rewrite
    limit: int = 50,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    tenant = get_current_user(request, db)  # fcg-rewrite
    orders = payment_service.get_payment_orders(  # fcg-rewrite
        db=db, tenant_id=str(tenant.id), order_type=order_type, status=status, limit=limit  # fcg-rewrite
    )
    return {"orders": orders}  # fcg-rewrite


@router.get("/subscription/status")  # fcg-rewrite
async def get_subscription_status(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant = get_current_user(request, db)  # fcg-rewrite
    subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
        TenantSubscription.tenant_id == tenant.id  # fcg-rewrite
    ).first()  # fcg-rewrite
    if not subscription:  # fcg-rewrite
        return {"subscription_type": "free", "is_active": False}  # fcg-rewrite
    payment = db.query(SubscriptionPayment).filter(  # fcg-rewrite
        and_(SubscriptionPayment.tenant_id == tenant.id, SubscriptionPayment.status == "active")  # fcg-rewrite
    ).first()  # fcg-rewrite
    return {  # fcg-rewrite
        "subscription_type": subscription.subscription_type,  # fcg-rewrite
        "is_active": subscription.subscription_type == "subscribed",  # fcg-rewrite
        "started_at": subscription.subscription_started_at.isoformat()  # fcg-rewrite
        if subscription.subscription_started_at else None,  # fcg-rewrite
        "expires_at": subscription.subscription_expires_at.isoformat()  # fcg-rewrite
        if subscription.subscription_expires_at else None,  # fcg-rewrite
        "cancel_at_period_end": payment.cancel_at_period_end if payment else False,  # fcg-rewrite
        "next_payment_date": payment.next_payment_date.isoformat()  # fcg-rewrite
        if payment and payment.next_payment_date else None,  # fcg-rewrite
    }


def _find_session_order(db: Session, tenant_id: object, session_id: str) -> Optional[PaymentOrder]:  # fcg-rewrite
    base = db.query(PaymentOrder).filter(PaymentOrder.tenant_id == tenant_id)  # fcg-rewrite
    for metadata_key in ("stripe_session_id", "trade_no"):  # fcg-rewrite
        order = base.filter(text(f"order_metadata->>'{metadata_key}' = :session_id")).params(  # fcg-rewrite
            session_id=session_id  # fcg-rewrite
        ).first()  # fcg-rewrite
        if order:  # fcg-rewrite
            return order  # fcg-rewrite
    return None  # fcg-rewrite


def _classify_order(db: Session, order: PaymentOrder) -> tuple[Optional[str], dict]:  # fcg-rewrite
    details = {}  # fcg-rewrite
    if order.provider_order_id.startswith("sub_"):  # fcg-rewrite
        return "subscription", details  # fcg-rewrite
    if order.provider_order_id.startswith("pkg_"):  # fcg-rewrite
        if order.package_id:  # fcg-rewrite
            details["package_id"] = str(order.package_id)  # fcg-rewrite
            purchase = db.query(PackagePurchase).filter(  # fcg-rewrite
                PackagePurchase.tenant_id == order.tenant_id,  # fcg-rewrite
                PackagePurchase.package_id == order.package_id,  # fcg-rewrite
            ).first()  # fcg-rewrite
            if purchase:  # fcg-rewrite
                details["purchase_status"] = purchase.status  # fcg-rewrite
        return "package", details  # fcg-rewrite
    if order.provider_order_id.startswith("quota_"):  # fcg-rewrite
        metadata = order.order_metadata or {}  # fcg-rewrite
        details.update(units=metadata.get("units"), calls=metadata.get("calls"))  # fcg-rewrite
        return "quota_purchase", details  # fcg-rewrite
    return None, details  # fcg-rewrite


async def _settle_checkout(db: Session, order: PaymentOrder, order_type: str, transaction_id: str):  # fcg-rewrite
    handlers = {  # fcg-rewrite
        "subscription": payment_service.handle_subscription_paid,  # fcg-rewrite
        "package": payment_service.handle_package_paid,  # fcg-rewrite
    }
    handler = handlers.get(order_type)  # fcg-rewrite
    if handler:  # fcg-rewrite
        return await handler(db=db, order_id=order.provider_order_id, transaction_id=transaction_id)  # fcg-rewrite
    return None  # fcg-rewrite


@router.get("/verify-session/{session_id}")  # fcg-rewrite
async def verify_payment_session(  # fcg-rewrite
    session_id: str, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        tenant = get_current_user(request, db)  # fcg-rewrite
        order = _find_session_order(db, tenant.id, session_id)  # fcg-rewrite
        if not order:  # fcg-rewrite
            return {"status": "not_found", "message": "Payment session not found"}  # fcg-rewrite
        order_type, details = _classify_order(db, order)  # fcg-rewrite
        if order.status == "pending" and order.payment_provider == "stripe":  # fcg-rewrite
            try:
                checkout = await stripe_service.get_checkout_session(session_id)  # fcg-rewrite
                if checkout and checkout.get("payment_status") == "paid":  # fcg-rewrite
                    transaction_id = checkout.get("payment_intent") or session_id  # fcg-rewrite
                    await _settle_checkout(db, order, order_type, transaction_id)  # fcg-rewrite
                    db.refresh(order)  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error("Stripe session lookup failed for %s: %s", session_id, exc)  # fcg-rewrite
        statuses = {"paid": "completed", "failed": "failed", "cancelled": "failed"}  # fcg-rewrite
        return {  # fcg-rewrite
            "status": statuses.get(order.status, "pending"),  # fcg-rewrite
            "order_type": order_type,  # fcg-rewrite
            "order_id": order.provider_order_id,  # fcg-rewrite
            "payment_status": order.status,  # fcg-rewrite
            "details": details,  # fcg-rewrite
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,  # fcg-rewrite
        }
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        logger.error("Payment verification error: %s", exc)  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Verification failed") from exc  # fcg-rewrite


async def _dispatch_paid(db: Session, order_id: str, transaction_id: str, paid_at=None):  # fcg-rewrite
    handlers = {  # fcg-rewrite
        "sub_": payment_service.handle_subscription_paid,  # fcg-rewrite
        "pkg_": payment_service.handle_package_paid,  # fcg-rewrite
        "quota_": payment_service.handle_quota_purchase_paid,  # fcg-rewrite
    }
    handler = next((value for prefix, value in handlers.items() if order_id.startswith(prefix)), None)  # fcg-rewrite
    if not handler:  # fcg-rewrite
        return None  # fcg-rewrite
    return await handler(db=db, order_id=order_id, transaction_id=transaction_id, paid_at=paid_at)  # fcg-rewrite


@router.post("/webhook/alipay")  # fcg-rewrite
async def alipay_webhook(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        params = dict(await request.form())  # fcg-rewrite
        if not alipay_service.verify_callback(params):  # fcg-rewrite
            return "fail"  # fcg-rewrite
        if params.get("trade_status") not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:  # fcg-rewrite
            return "success"  # fcg-rewrite
        callback = alipay_service.parse_callback(params)  # fcg-rewrite
        result = await _dispatch_paid(  # fcg-rewrite
            db, callback["order_id"], callback["transaction_id"], callback.get("paid_at")  # fcg-rewrite
        )
        return "success" if result and result.get("success") else "fail"  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("Alipay webhook error: %s", exc)  # fcg-rewrite
        return "fail"  # fcg-rewrite


def _stripe_payment(db: Session, stripe_subscription_id: str) -> Optional[SubscriptionPayment]:  # fcg-rewrite
    if not stripe_subscription_id:  # fcg-rewrite
        return None  # fcg-rewrite
    return db.query(SubscriptionPayment).filter(  # fcg-rewrite
        SubscriptionPayment.stripe_subscription_id == stripe_subscription_id  # fcg-rewrite
    ).first()  # fcg-rewrite


async def _stripe_checkout_completed(db: Session, event: dict) -> None:  # fcg-rewrite
    session = stripe_service.parse_checkout_completed(event)  # fcg-rewrite
    order_type = session.get("metadata", {}).get("order_type")  # fcg-rewrite
    order = db.query(PaymentOrder).filter(  # fcg-rewrite
        text("order_metadata->>'stripe_session_id' = :session_id")  # fcg-rewrite
    ).params(session_id=session["session_id"]).first()  # fcg-rewrite
    if not order:  # fcg-rewrite
        return
    if order_type == "subscription":  # fcg-rewrite
        payment = db.query(SubscriptionPayment).filter(  # fcg-rewrite
            SubscriptionPayment.payment_order_id == order.id  # fcg-rewrite
        ).first()  # fcg-rewrite
        if payment:  # fcg-rewrite
            payment.stripe_subscription_id = session.get("subscription_id")  # fcg-rewrite
            payment.stripe_customer_id = session.get("customer_id")  # fcg-rewrite
            db.commit()  # fcg-rewrite
    await _settle_checkout(  # fcg-rewrite
        db, order, order_type, session.get("payment_intent_id") or session["session_id"]  # fcg-rewrite
    )


def _stripe_invoice_paid(db: Session, event: dict) -> None:  # fcg-rewrite
    invoice = stripe_service.parse_invoice_paid(event)  # fcg-rewrite
    payment = _stripe_payment(db, invoice.get("subscription_id"))  # fcg-rewrite
    if not payment:  # fcg-rewrite
        return
    payment.billing_cycle_start = invoice.get("period_start")  # fcg-rewrite
    payment.billing_cycle_end = invoice.get("period_end")  # fcg-rewrite
    payment.next_payment_date = invoice.get("period_end")  # fcg-rewrite
    subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
        TenantSubscription.tenant_id == payment.tenant_id  # fcg-rewrite
    ).first()  # fcg-rewrite
    if subscription:  # fcg-rewrite
        subscription.subscription_expires_at = invoice.get("period_end")  # fcg-rewrite
    db.commit()  # fcg-rewrite


def _stripe_subscription_updated(db: Session, event: dict) -> None:  # fcg-rewrite
    data = event["data"]["object"]  # fcg-rewrite
    payment = _stripe_payment(db, data.get("id"))  # fcg-rewrite
    if not payment or not data.get("status"):  # fcg-rewrite
        return
    payment.cancel_at_period_end = data.get("cancel_at_period_end", False)  # fcg-rewrite
    period_end = data.get("current_period_end")  # fcg-rewrite
    subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
        TenantSubscription.tenant_id == payment.tenant_id  # fcg-rewrite
    ).first()  # fcg-rewrite
    if subscription and period_end:  # fcg-rewrite
        subscription.subscription_expires_at = datetime.fromtimestamp(period_end)  # fcg-rewrite
    db.commit()  # fcg-rewrite


def _stripe_subscription_deleted(db: Session, event: dict) -> None:  # fcg-rewrite
    payment = _stripe_payment(db, event["data"]["object"].get("id"))  # fcg-rewrite
    if not payment:  # fcg-rewrite
        return
    payment.status = "cancelled"  # fcg-rewrite
    payment.cancelled_at = datetime.utcnow()  # fcg-rewrite
    subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
        TenantSubscription.tenant_id == payment.tenant_id  # fcg-rewrite
    ).first()  # fcg-rewrite
    if subscription:  # fcg-rewrite
        subscription.subscription_type = "free"  # fcg-rewrite
        subscription.monthly_quota = billing_service.SUBSCRIPTION_CONFIGS["free"]["monthly_quota"]  # fcg-rewrite
        subscription.subscription_tier = 0  # fcg-rewrite
    db.commit()  # fcg-rewrite


@router.post("/webhook/stripe")  # fcg-rewrite
async def stripe_webhook(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    stripe_signature: str = Header(None, alias="Stripe-Signature"),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        event = stripe_service.verify_webhook(await request.body(), stripe_signature)  # fcg-rewrite
        event_type = event["type"]  # fcg-rewrite
        if event_type == "checkout.session.completed":  # fcg-rewrite
            await _stripe_checkout_completed(db, event)  # fcg-rewrite
        elif event_type == "invoice.paid":  # fcg-rewrite
            _stripe_invoice_paid(db, event)  # fcg-rewrite
        elif event_type == "invoice.payment_failed":  # fcg-rewrite
            invoice = stripe_service.parse_invoice_paid(event)  # fcg-rewrite
            if _stripe_payment(db, invoice.get("subscription_id")):  # fcg-rewrite
                logger.warning("Stripe recurring payment failed: %s", invoice.get("subscription_id"))  # fcg-rewrite
        elif event_type == "customer.subscription.updated":  # fcg-rewrite
            _stripe_subscription_updated(db, event)  # fcg-rewrite
        elif event_type == "customer.subscription.deleted":  # fcg-rewrite
            _stripe_subscription_deleted(db, event)  # fcg-rewrite
        return {"received": True}  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("Stripe webhook error: %s", exc)  # fcg-rewrite
        raise HTTPException(status_code=400, detail=str(exc)) from exc  # fcg-rewrite


@router.post("/webhook/alipay/agreement")  # fcg-rewrite
async def alipay_agreement_webhook(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        params = dict(await request.form())  # fcg-rewrite
        if not alipay_service.verify_callback(params):  # fcg-rewrite
            return "fail"  # fcg-rewrite
        notify_type = params.get("notify_type", "")  # fcg-rewrite
        agreement_no = params.get("agreement_no")  # fcg-rewrite
        if notify_type == "dut_user_sign" and params.get("status") == "NORMAL" and agreement_no:  # fcg-rewrite
            order = db.query(PaymentOrder).filter(  # fcg-rewrite
                PaymentOrder.provider_order_id == params.get("external_agreement_no")  # fcg-rewrite
            ).first()  # fcg-rewrite
            subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
                TenantSubscription.tenant_id == order.tenant_id  # fcg-rewrite
            ).first() if order else None  # fcg-rewrite
            if subscription:  # fcg-rewrite
                subscription.alipay_agreement_no = agreement_no  # fcg-rewrite
                db.commit()  # fcg-rewrite
        elif notify_type == "dut_user_unsign" and agreement_no:  # fcg-rewrite
            subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
                TenantSubscription.alipay_agreement_no == agreement_no  # fcg-rewrite
            ).first()  # fcg-rewrite
            if subscription:  # fcg-rewrite
                subscription.subscription_type = "free"  # fcg-rewrite
                subscription.monthly_quota = billing_service.SUBSCRIPTION_CONFIGS["free"]["monthly_quota"]  # fcg-rewrite
                subscription.subscription_tier = 0  # fcg-rewrite
                subscription.alipay_agreement_no = None  # fcg-rewrite
                db.commit()  # fcg-rewrite
        return "success"  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("Alipay agreement webhook error: %s", exc)  # fcg-rewrite
        return "fail"  # fcg-rewrite
