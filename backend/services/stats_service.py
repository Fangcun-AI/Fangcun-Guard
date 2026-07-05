"""Dashboard aggregation over persisted detection records."""

import json
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import DetectionResult
from services.risk_policy import highest_risk_level
from utils.logger import setup_logger

logger = setup_logger()

RISK_LEVELS = ("high_risk", "medium_risk", "low_risk", "no_risk")


class StatsService:
    """Read-only statistics facade for the admin dashboard."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_stats(self, application_id: uuid.UUID = None) -> Dict[str, Any]:
        try:
            records = self._scoped(self.db.query(DetectionResult), application_id)
            risk_rows = self._scoped(
                self.db.query(
                    DetectionResult.security_risk_level,
                    DetectionResult.compliance_risk_level,
                    DetectionResult.data_risk_level,
                ),
                application_id,
            ).all()
            distribution = Counter(
                self._get_highest_risk_level(*risk_row) for risk_row in risk_rows
            )
            result = {
                "total_requests": records.count(),
                "security_risks": records.filter(
                    DetectionResult.security_risk_level != "no_risk"
                ).count(),
                "compliance_risks": records.filter(
                    DetectionResult.compliance_risk_level != "no_risk"
                ).count(),
                "data_leaks": records.filter(
                    DetectionResult.data_risk_level != "no_risk"
                ).count(),
                "high_risk_count": distribution["high_risk"],
                "medium_risk_count": distribution["medium_risk"],
                "low_risk_count": distribution["low_risk"],
                "safe_count": distribution["no_risk"],
                "risk_distribution": {
                    level: distribution[level] for level in RISK_LEVELS
                },
                "daily_trends": self._get_daily_trends(7, application_id),
            }
            return result
        except Exception as exc:
            logger.error(f"Failed to build dashboard statistics: {exc}")
            return self._get_empty_stats()

    def _get_daily_trends(
        self, days: int, application_id: uuid.UUID = None
    ) -> List[Dict[str, Any]]:
        try:
            today = datetime.now().date()
            first_day = today - timedelta(days=days - 1)
            query = self.db.query(
                func.date(DetectionResult.created_at).label("date"),
                DetectionResult.security_risk_level,
                DetectionResult.compliance_risk_level,
                DetectionResult.data_risk_level,
            ).filter(func.date(DetectionResult.created_at) >= first_day)
            rows = self._scoped(query, application_id).all()

            buckets = {}
            for row in rows:
                bucket = buckets.setdefault(str(row.date), self._empty_day())
                bucket["total"] += 1
                level = self._get_highest_risk_level(
                    row.security_risk_level,
                    row.compliance_risk_level,
                    row.data_risk_level,
                )
                bucket["safe" if level == "no_risk" else level] += 1

            return [
                {"date": day.isoformat(), **buckets.get(str(day), self._empty_day())}
                for day in (first_day + timedelta(days=offset) for offset in range(days))
            ]
        except Exception as exc:
            logger.error(f"Failed to build daily trends: {exc}")
            return []

    def get_category_distribution(
        self,
        start_date: str = None,
        end_date: str = None,
        application_id: uuid.UUID = None,
    ) -> List[Dict[str, Any]]:
        try:
            query = self.db.query(DetectionResult).filter(
                (DetectionResult.security_risk_level != "no_risk")
                | (DetectionResult.compliance_risk_level != "no_risk")
            )
            query = self._scoped(query, application_id)
            if start_date:
                query = query.filter(func.date(DetectionResult.created_at) >= start_date)
            if end_date:
                query = query.filter(func.date(DetectionResult.created_at) <= end_date)

            counts = Counter()
            for security_categories, compliance_categories in query.with_entities(
                DetectionResult.security_categories,
                DetectionResult.compliance_categories,
            ).all():
                counts.update(self._decode_categories(security_categories))
                counts.update(self._decode_categories(compliance_categories))
            return [
                {"name": name, "value": count}
                for name, count in counts.most_common(10)
            ]
        except Exception as exc:
            logger.error(f"Failed to build category distribution: {exc}")
            return []

    @staticmethod
    def _get_highest_risk_level(
        security_risk: str, compliance_risk: str, data_risk: str = "no_risk"
    ) -> str:
        return highest_risk_level((security_risk, compliance_risk, data_risk))

    @staticmethod
    def _decode_categories(value) -> List[str]:
        try:
            categories = json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(categories, list):
            return []
        return [
            category
            for category in categories
            if isinstance(category, str) and category.strip()
        ]

    @staticmethod
    def _empty_day() -> Dict[str, int]:
        return {"total": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0, "safe": 0}

    @classmethod
    def _get_empty_stats(cls) -> Dict[str, Any]:
        return {
            "total_requests": 0,
            "security_risks": 0,
            "compliance_risks": 0,
            "data_leaks": 0,
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "safe_count": 0,
            "risk_distribution": {level: 0 for level in RISK_LEVELS},
            "daily_trends": [],
        }

    @staticmethod
    def _scoped(query, application_id):
        if application_id is None:
            return query
        return query.filter(DetectionResult.application_id == application_id)
