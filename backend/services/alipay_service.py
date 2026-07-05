"""Alipay SDK adapter for checkout and recurring billing."""

import logging  # fcg-rewrite
from datetime import datetime  # fcg-rewrite
from typing import Any, Dict  # fcg-rewrite

try:
    from services.alipay_rsa_patch import apply_alipay_rsa_patch  # fcg-rewrite

    apply_alipay_rsa_patch()  # fcg-rewrite
except Exception as error:  # fcg-rewrite
    print(f"Alipay RSA patch was not applied: {error}")  # fcg-rewrite

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig  # fcg-rewrite
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient  # fcg-rewrite
from alipay.aop.api.domain.AlipayTradeCloseModel import AlipayTradeCloseModel  # fcg-rewrite
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel  # fcg-rewrite
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel  # fcg-rewrite
from alipay.aop.api.request.AlipayTradeCloseRequest import AlipayTradeCloseRequest  # fcg-rewrite
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest  # fcg-rewrite
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest  # fcg-rewrite
from alipay.aop.api.response.AlipayTradeCloseResponse import AlipayTradeCloseResponse  # fcg-rewrite
from alipay.aop.api.response.AlipayTradeQueryResponse import AlipayTradeQueryResponse  # fcg-rewrite
from alipay.aop.api.util.SignatureUtils import verify_with_rsa  # fcg-rewrite

from config import settings  # fcg-rewrite
from utils.logger import get_logger  # fcg-rewrite

logger = get_logger(__name__)  # fcg-rewrite
logging.getLogger("alipay").setLevel(logging.INFO)  # fcg-rewrite


def _model(model_type, **values):  # fcg-rewrite
    model = model_type()  # fcg-rewrite
    for field, value in values.items():  # fcg-rewrite
        setattr(model, field, value)  # fcg-rewrite
    return model  # fcg-rewrite


class AlipayClient:  # fcg-rewrite
    def __init__(self):  # fcg-rewrite
        self.app_id = settings.alipay_app_id  # fcg-rewrite
        self.private_key = settings.alipay_private_key  # fcg-rewrite
        self.public_key = settings.alipay_public_key  # fcg-rewrite
        self.notify_url = settings.alipay_notify_url  # fcg-rewrite
        self.return_url = settings.alipay_return_url  # fcg-rewrite
        self.gateway = settings.alipay_gateway  # fcg-rewrite
        self._client = None  # fcg-rewrite

    def _get_client(self) -> DefaultAlipayClient:  # fcg-rewrite
        if self._client:  # fcg-rewrite
            return self._client  # fcg-rewrite
        if not all((self.app_id, self.private_key, self.public_key)):  # fcg-rewrite
            raise ValueError("Alipay is not configured")  # fcg-rewrite
        config = AlipayClientConfig()  # fcg-rewrite
        config.server_url = self.gateway  # fcg-rewrite
        config.app_id = self.app_id  # fcg-rewrite
        config.app_private_key = self.private_key  # fcg-rewrite
        config.alipay_public_key = self.public_key  # fcg-rewrite
        self._client = DefaultAlipayClient(alipay_client_config=config, logger=logger)  # fcg-rewrite
        return self._client  # fcg-rewrite

    def _execute(self, request, response_type):  # fcg-rewrite
        content = self._get_client().execute(request)  # fcg-rewrite
        if not content:  # fcg-rewrite
            return None  # fcg-rewrite
        response = response_type()  # fcg-rewrite
        response.parse_response_content(content)  # fcg-rewrite
        return response  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _failure(response) -> Dict[str, Any]:  # fcg-rewrite
        return {  # fcg-rewrite
            field: getattr(response, field, None)  # fcg-rewrite
            for field in ("code", "msg", "sub_code", "sub_msg")  # fcg-rewrite
            if getattr(response, field, None) is not None  # fcg-rewrite
        } | {"success": False}  # fcg-rewrite

    async def create_subscription_order(  # fcg-rewrite
        self,
        order_id: str,  # fcg-rewrite
        amount: float,  # fcg-rewrite
        subject: str = "象信AI安全护栏订阅服务",  # fcg-rewrite
        body: str = "象信AI安全护栏月度订阅",  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        model = _model(  # fcg-rewrite
            AlipayTradePagePayModel,  # fcg-rewrite
            out_trade_no=order_id,  # fcg-rewrite
            total_amount=f"{amount:.2f}",  # fcg-rewrite
            subject=subject,  # fcg-rewrite
            body=body,  # fcg-rewrite
            product_code="FAST_INSTANT_TRADE_PAY",  # fcg-rewrite
        )
        request = AlipayTradePagePayRequest(biz_model=model)  # fcg-rewrite
        request.notify_url = self.notify_url  # fcg-rewrite
        request.return_url = self.return_url  # fcg-rewrite
        return {  # fcg-rewrite
            "order_id": order_id,  # fcg-rewrite
            "payment_url": self._get_client().page_execute(request, http_method="GET"),  # fcg-rewrite
            "amount": amount,  # fcg-rewrite
            "currency": "CNY",  # fcg-rewrite
        }

    async def create_package_order(self, order_id: str, amount: float, package_name: str) -> Dict[str, Any]:  # fcg-rewrite
        return await self.create_subscription_order(  # fcg-rewrite
            order_id, amount, f"象信AI安全护栏 - {package_name}", f"购买扫描器包: {package_name}"  # fcg-rewrite
        )

    async def query_order(self, order_id: str) -> Dict[str, Any]:  # fcg-rewrite
        try:
            request = AlipayTradeQueryRequest(  # fcg-rewrite
                biz_model=_model(AlipayTradeQueryModel, out_trade_no=order_id)  # fcg-rewrite
            )
            response = self._execute(request, AlipayTradeQueryResponse)  # fcg-rewrite
            if not response:  # fcg-rewrite
                return {"success": False, "error": "No response from Alipay"}  # fcg-rewrite
            if not response.is_success():  # fcg-rewrite
                return self._failure(response)  # fcg-rewrite
            return {"success": True} | {  # fcg-rewrite
                field: getattr(response, field)  # fcg-rewrite
                for field in ("trade_no", "out_trade_no", "trade_status", "total_amount", "buyer_user_id")  # fcg-rewrite
            }
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to query Alipay order %s: %s", order_id, error)  # fcg-rewrite
            return {"success": False, "error": str(error)}  # fcg-rewrite

    async def close_order(self, order_id: str) -> Dict[str, Any]:  # fcg-rewrite
        try:
            request = AlipayTradeCloseRequest(  # fcg-rewrite
                biz_model=_model(AlipayTradeCloseModel, out_trade_no=order_id)  # fcg-rewrite
            )
            response = self._execute(request, AlipayTradeCloseResponse)  # fcg-rewrite
            if not response:  # fcg-rewrite
                return {"success": False, "error": "No response from Alipay"}  # fcg-rewrite
            return {"success": True, "trade_no": response.trade_no} if response.is_success() else self._failure(response)  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to close Alipay order %s: %s", order_id, error)  # fcg-rewrite
            return {"success": False, "error": str(error)}  # fcg-rewrite

    def verify_callback(self, params: Dict[str, Any]) -> bool:  # fcg-rewrite
        signature = params.get("sign", "")  # fcg-rewrite
        if not self.public_key or not signature:  # fcg-rewrite
            return False  # fcg-rewrite
        values = {key: value for key, value in params.items() if key not in {"sign", "sign_type"}}  # fcg-rewrite
        signed = "&".join(f"{key}={value}" for key, value in sorted(values.items()) if value)  # fcg-rewrite
        try:
            return verify_with_rsa(self.public_key, signed.encode("utf-8"), signature)  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Alipay callback signature check failed: %s", error)  # fcg-rewrite
            return False  # fcg-rewrite

    async def create_subscription_agreement(  # fcg-rewrite
        self, order_id: str, amount: float, tier_name: str = "订阅服务"  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        try:
            from alipay.aop.api.domain.AlipayUserAgreementPageSignModel import AlipayUserAgreementPageSignModel  # fcg-rewrite
            from alipay.aop.api.domain.PeriodRuleParams import PeriodRuleParams  # fcg-rewrite
            from alipay.aop.api.request.AlipayUserAgreementPageSignRequest import AlipayUserAgreementPageSignRequest  # fcg-rewrite
        except ImportError:  # fcg-rewrite
            return await self.create_subscription_order(  # fcg-rewrite
                order_id, amount, f"象信AI安全护栏 - {tier_name}", f"订阅套餐: {tier_name}"  # fcg-rewrite
            )
        period = _model(  # fcg-rewrite
            PeriodRuleParams,  # fcg-rewrite
            period_type="MONTH",  # fcg-rewrite
            period=1,  # fcg-rewrite
            single_amount=f"{amount:.2f}",  # fcg-rewrite
            total_amount=f"{amount * 12:.2f}",  # fcg-rewrite
            total_payments=12,  # fcg-rewrite
            execute_time=datetime.now().strftime("%Y-%m-%d"),  # fcg-rewrite
        )
        model = _model(  # fcg-rewrite
            AlipayUserAgreementPageSignModel,  # fcg-rewrite
            personal_product_code="CYCLE_PAY_AUTH",  # fcg-rewrite
            sign_scene="INDUSTRY|DIGITAL_MEDIA",  # fcg-rewrite
            external_agreement_no=order_id,  # fcg-rewrite
            access_params={"channel": "ALIPAYAPP"},  # fcg-rewrite
            period_rule_params=period,  # fcg-rewrite
            product_code="GENERAL_WITHHOLDING",  # fcg-rewrite
        )
        request = AlipayUserAgreementPageSignRequest(biz_model=model)  # fcg-rewrite
        request.return_url = self.return_url  # fcg-rewrite
        request.notify_url = self.notify_url  # fcg-rewrite
        return {"order_id": order_id, "signing_url": self._get_client().page_execute(request, http_method="GET"), "amount": amount}  # fcg-rewrite

    async def execute_agreement_pay(self, agreement_no: str, amount: float, order_id: str) -> Dict[str, Any]:  # fcg-rewrite
        try:
            from alipay.aop.api.domain.AlipayTradePayModel import AlipayTradePayModel  # fcg-rewrite
            from alipay.aop.api.request.AlipayTradePayRequest import AlipayTradePayRequest  # fcg-rewrite
            from alipay.aop.api.response.AlipayTradePayResponse import AlipayTradePayResponse  # fcg-rewrite
        except ImportError:  # fcg-rewrite
            return {"success": False, "error": "Agreement pay not supported"}  # fcg-rewrite
        try:
            model = _model(  # fcg-rewrite
                AlipayTradePayModel,  # fcg-rewrite
                out_trade_no=order_id,  # fcg-rewrite
                total_amount=f"{amount:.2f}",  # fcg-rewrite
                subject="象信AI安全护栏月度订阅续费",  # fcg-rewrite
                product_code="GENERAL_WITHHOLDING",  # fcg-rewrite
                agreement_params={"agreement_no": agreement_no},  # fcg-rewrite
            )
            response = self._execute(AlipayTradePayRequest(biz_model=model), AlipayTradePayResponse)  # fcg-rewrite
            if not response:  # fcg-rewrite
                return {"success": False, "error": "No response from Alipay"}  # fcg-rewrite
            return {"success": True, "trade_no": response.trade_no, "out_trade_no": response.out_trade_no} if response.is_success() else self._failure(response)  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            return {"success": False, "error": str(error)}  # fcg-rewrite

    async def unsign_agreement(self, agreement_no: str) -> Dict[str, Any]:  # fcg-rewrite
        try:
            from alipay.aop.api.domain.AlipayUserAgreementUnsignModel import AlipayUserAgreementUnsignModel  # fcg-rewrite
            from alipay.aop.api.request.AlipayUserAgreementUnsignRequest import AlipayUserAgreementUnsignRequest  # fcg-rewrite
            from alipay.aop.api.response.AlipayUserAgreementUnsignResponse import AlipayUserAgreementUnsignResponse  # fcg-rewrite
        except ImportError:  # fcg-rewrite
            return {"success": False, "error": "Agreement unsign not supported"}  # fcg-rewrite
        try:
            model = _model(AlipayUserAgreementUnsignModel, agreement_no=agreement_no, personal_product_code="CYCLE_PAY_AUTH")  # fcg-rewrite
            response = self._execute(AlipayUserAgreementUnsignRequest(biz_model=model), AlipayUserAgreementUnsignResponse)  # fcg-rewrite
            if not response:  # fcg-rewrite
                return {"success": False, "error": "No response from Alipay"}  # fcg-rewrite
            return {"success": True} if response.is_success() else self._failure(response)  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            return {"success": False, "error": str(error)}  # fcg-rewrite

    def parse_callback(self, params: Dict[str, Any]) -> Dict[str, Any]:  # fcg-rewrite
        return {  # fcg-rewrite
            "order_id": params.get("out_trade_no"),  # fcg-rewrite
            "transaction_id": params.get("trade_no"),  # fcg-rewrite
            "amount": float(params.get("total_amount", 0)),  # fcg-rewrite
            "status": params.get("trade_status"),  # fcg-rewrite
            "paid_at": params.get("gmt_payment"),  # fcg-rewrite
            "buyer_id": params.get("buyer_id"),  # fcg-rewrite
        }


alipay_service = AlipayClient()  # fcg-rewrite
