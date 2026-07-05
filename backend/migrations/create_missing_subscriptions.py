#!/usr/bin/env python3
"""
Migration script to create subscriptions for existing tenants
This script creates free subscriptions for any tenants that don't have one yet.
"""

import os  # fcg-rewrite
import sys  # fcg-rewrite
from datetime import datetime, timedelta, timezone  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))  # fcg-rewrite

from database.connection import SessionLocal  # fcg-rewrite
from database.models import Tenant, TenantSubscription  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


def calculate_next_reset_date(from_date: datetime = None) -> datetime:  # fcg-rewrite
    """Calculate the next quota reset date"""
    if from_date is None:  # fcg-rewrite
        from_date = datetime.now()  # fcg-rewrite

    # Get the day of month from subscription start
    reset_day = from_date.day  # fcg-rewrite

    # Calculate next reset based on current time
    year = from_date.year  # fcg-rewrite
    month = from_date.month  # fcg-rewrite

    # Move to next month
    if month == 12:  # fcg-rewrite
        month = 1  # fcg-rewrite
        year += 1  # fcg-rewrite
    else:
        month += 1  # fcg-rewrite

    # Handle months with fewer days
    while True:  # fcg-rewrite
        try:
            next_reset = datetime(year, month, reset_day, 0, 0, 0, tzinfo=timezone.utc)  # fcg-rewrite
            break
        except ValueError:  # fcg-rewrite
            # Day doesn't exist in this month, use last day of month
            if month == 2:  # fcg-rewrite
                # February - check for leap year
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):  # fcg-rewrite
                    reset_day = 29  # fcg-rewrite
                else:
                    reset_day = 28  # fcg-rewrite
            elif month in [4, 6, 9, 11]:  # fcg-rewrite
                reset_day = 30  # fcg-rewrite
            else:
                reset_day = 31  # fcg-rewrite

    return next_reset  # fcg-rewrite


def create_missing_subscriptions():  # fcg-rewrite
    """Create free subscriptions for tenants that don't have one"""
    db = SessionLocal()  # fcg-rewrite
    created_count = 0  # fcg-rewrite
    skipped_count = 0  # fcg-rewrite
    error_count = 0  # fcg-rewrite

    try:
        # Get all active and verified tenants
        tenants = db.query(Tenant).filter(  # fcg-rewrite
            Tenant.is_active == True,  # fcg-rewrite
            Tenant.is_verified == True  # fcg-rewrite
        ).all()

        logger.info(f"Found {len(tenants)} active and verified tenants")  # fcg-rewrite

        for tenant in tenants:  # fcg-rewrite
            try:
                # Check if subscription already exists
                existing = db.query(TenantSubscription).filter(  # fcg-rewrite
                    TenantSubscription.tenant_id == tenant.id  # fcg-rewrite
                ).first()  # fcg-rewrite

                if existing:  # fcg-rewrite
                    logger.debug(f"Subscription already exists for tenant {tenant.email}")  # fcg-rewrite
                    skipped_count += 1  # fcg-rewrite
                    continue  # fcg-rewrite

                # Create free subscription
                current_time = datetime.now(timezone.utc)  # fcg-rewrite
                reset_date = calculate_next_reset_date(current_time)  # fcg-rewrite

                subscription = TenantSubscription(  # fcg-rewrite
                    tenant_id=tenant.id,  # fcg-rewrite
                    subscription_type='free',  # fcg-rewrite
                    monthly_quota=1000,  # fcg-rewrite
                    current_month_usage=0,  # fcg-rewrite
                    usage_reset_at=reset_date,  # fcg-rewrite
                    created_at=current_time,  # fcg-rewrite
                    updated_at=current_time  # fcg-rewrite
                )

                db.add(subscription)  # fcg-rewrite
                db.commit()  # fcg-rewrite

                logger.info(f"Created free subscription for tenant {tenant.email}")  # fcg-rewrite
                created_count += 1  # fcg-rewrite

            except Exception as e:  # fcg-rewrite
                logger.error(f"Failed to create subscription for tenant {tenant.email}: {e}")  # fcg-rewrite
                db.rollback()  # fcg-rewrite
                error_count += 1  # fcg-rewrite
                continue  # fcg-rewrite

        logger.info(f"""
Migration completed:
- Created: {created_count} subscriptions
- Skipped: {skipped_count} (already exist)
- Errors: {error_count}
""")

        return created_count, skipped_count, error_count  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        logger.error(f"Migration failed: {e}")  # fcg-rewrite
        raise
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite


if __name__ == "__main__":  # fcg-rewrite
    print("Creating missing tenant subscriptions...")  # fcg-rewrite
    created, skipped, errors = create_missing_subscriptions()  # fcg-rewrite
    print(f"\nResults:")  # fcg-rewrite
    print(f"  Created: {created}")  # fcg-rewrite
    print(f"  Skipped: {skipped}")  # fcg-rewrite
    print(f"  Errors: {errors}")  # fcg-rewrite

    if errors > 0:  # fcg-rewrite
        sys.exit(1)  # fcg-rewrite
