"""Create and retire default answer templates for detection sources."""

from typing import Dict, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import Blacklist, ResponseTemplate, Scanner  # fcg-rewrite
from services.risk_policy import CATEGORY_LABELS  # fcg-rewrite
from utils.i18n_loader import get_translation  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class ResponseTemplateService:  # fcg-rewrite
    """Small persistence adapter for scanner-linked response templates."""

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite

    def create_template_for_official_scanner(  # fcg-rewrite
        self, scanner: Scanner, application_id: UUID, tenant_id: UUID  # fcg-rewrite
    ) -> Optional[ResponseTemplate]:  # fcg-rewrite
        return self._create(  # fcg-rewrite
            scanner_type="official_scanner",  # fcg-rewrite
            identifier=scanner.tag,  # fcg-rewrite
            name=scanner.name,  # fcg-rewrite
            risk_level=scanner.default_risk_level,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            category=scanner.tag,  # fcg-rewrite
            content=self._get_default_content_for_official_scanner(scanner.tag),  # fcg-rewrite
        )

    def create_template_for_custom_scanner(  # fcg-rewrite
        self, scanner: Scanner, application_id: UUID, tenant_id: UUID  # fcg-rewrite
    ) -> Optional[ResponseTemplate]:  # fcg-rewrite
        return self._create_scanner_template(  # fcg-rewrite
            "custom_scanner", scanner, application_id, tenant_id  # fcg-rewrite
        )

    def create_template_for_marketplace_scanner(  # fcg-rewrite
        self, scanner: Scanner, application_id: UUID, tenant_id: UUID  # fcg-rewrite
    ) -> Optional[ResponseTemplate]:  # fcg-rewrite
        return self._create_scanner_template(  # fcg-rewrite
            "marketplace_scanner", scanner, application_id, tenant_id  # fcg-rewrite
        )

    def create_template_for_blacklist(  # fcg-rewrite
        self, blacklist: Blacklist, application_id: UUID, tenant_id: UUID  # fcg-rewrite
    ) -> Optional[ResponseTemplate]:  # fcg-rewrite
        return self._create(  # fcg-rewrite
            scanner_type="blacklist",  # fcg-rewrite
            identifier=blacklist.name,  # fcg-rewrite
            name=blacklist.name,  # fcg-rewrite
            risk_level="high_risk",  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
        )

    def delete_template_for_scanner(  # fcg-rewrite
        self, scanner_tag: str, scanner_type: str, application_id: UUID  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        return self._delete(scanner_type, scanner_tag, application_id)  # fcg-rewrite

    def delete_template_for_blacklist(  # fcg-rewrite
        self, blacklist_name: str, application_id: UUID  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        return self._delete("blacklist", blacklist_name, application_id)  # fcg-rewrite

    def _create_scanner_template(  # fcg-rewrite
        self, scanner_type: str, scanner: Scanner, application_id: UUID, tenant_id: UUID  # fcg-rewrite
    ) -> Optional[ResponseTemplate]:  # fcg-rewrite
        return self._create(  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            identifier=scanner.tag,  # fcg-rewrite
            name=scanner.name,  # fcg-rewrite
            risk_level=scanner.default_risk_level,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
        )

    def _create(  # fcg-rewrite
        self,
        *,
        scanner_type: str,  # fcg-rewrite
        identifier: str,  # fcg-rewrite
        name: str,  # fcg-rewrite
        risk_level: str,  # fcg-rewrite
        application_id: UUID,  # fcg-rewrite
        tenant_id: UUID,  # fcg-rewrite
        category: Optional[str] = None,  # fcg-rewrite
        content: Optional[Dict[str, str]] = None,  # fcg-rewrite
    ) -> Optional[ResponseTemplate]:  # fcg-rewrite
        source_identity = (  # fcg-rewrite
            ((ResponseTemplate.scanner_type == scanner_type)  # fcg-rewrite
            & (ResponseTemplate.scanner_identifier == identifier))  # fcg-rewrite
            | (ResponseTemplate.scanner_name == name)  # fcg-rewrite
            | (ResponseTemplate.category == identifier)  # fcg-rewrite
        )
        existing = (  # fcg-rewrite
            self.db.query(ResponseTemplate)  # fcg-rewrite
            .filter(  # fcg-rewrite
                ResponseTemplate.application_id == application_id,  # fcg-rewrite
                ResponseTemplate.tenant_id == tenant_id,  # fcg-rewrite
                source_identity,  # fcg-rewrite
            )
            .first()  # fcg-rewrite
        )
        if existing:  # fcg-rewrite
            return None  # fcg-rewrite

        template = ResponseTemplate(  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            category=category,  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            scanner_identifier=identifier,  # fcg-rewrite
            scanner_name=name,  # fcg-rewrite
            risk_level=risk_level,  # fcg-rewrite
            template_content=content or self._get_default_content_for_scanner(name),  # fcg-rewrite
            is_default=True,  # fcg-rewrite
            is_active=True,  # fcg-rewrite
        )
        self.db.add(template)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        self.db.refresh(template)  # fcg-rewrite
        logger.info(f"Created template for {scanner_type}:{identifier} in app {application_id}")  # fcg-rewrite
        return template  # fcg-rewrite

    def _delete(self, scanner_type: str, identifier: str, application_id: UUID) -> bool:  # fcg-rewrite
        template = (  # fcg-rewrite
            self.db.query(ResponseTemplate)  # fcg-rewrite
            .filter(  # fcg-rewrite
                ResponseTemplate.application_id == application_id,  # fcg-rewrite
                ResponseTemplate.scanner_type == scanner_type,  # fcg-rewrite
                ResponseTemplate.scanner_identifier == identifier,  # fcg-rewrite
            )
            .first()  # fcg-rewrite
        )
        if not template:  # fcg-rewrite
            return False  # fcg-rewrite
        self.db.delete(template)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        logger.info(f"Deleted template for {scanner_type}:{identifier} in app {application_id}")  # fcg-rewrite
        return True  # fcg-rewrite

    def _get_default_content_for_scanner(self, scanner_name: str) -> Dict[str, str]:  # fcg-rewrite
        return {  # fcg-rewrite
            language: self._translated_template(language).replace(  # fcg-rewrite
                "{scanner_name}", scanner_name  # fcg-rewrite
            )
            for language in ("en", "zh")  # fcg-rewrite
        }

    def _get_default_content_for_official_scanner(self, tag: str) -> Dict[str, str]:  # fcg-rewrite
        return self._get_default_content_for_scanner(CATEGORY_LABELS.get(tag, tag))  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _translated_template(language: str) -> str:  # fcg-rewrite
        try:
            return get_translation(  # fcg-rewrite
                language, "guardrail", "responseTemplates", "securityRisk"  # fcg-rewrite
            )
        except KeyError:  # fcg-rewrite
            return get_translation(language, "guardrail", "responseTemplates", "default")  # fcg-rewrite
