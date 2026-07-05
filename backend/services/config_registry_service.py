"""CRUD helpers for configuration registries used by config_api."""

from database.models import Blacklist, ResponseTemplate, Scanner, Whitelist  # fcg-rewrite
from models.responses import BlacklistResponse, ResponseTemplateResponse, WhitelistResponse  # fcg-rewrite
from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite
from services.keyword_cache import keyword_cache  # fcg-rewrite
from services.response_template_service import ResponseTemplateService  # fcg-rewrite
from services.template_cache import template_cache  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


class ConfigRegistryService:  # fcg-rewrite
    """Own blacklist, whitelist, and response-template persistence flows."""

    def __init__(self, db) -> None:  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self._template_service = ResponseTemplateService(db)  # fcg-rewrite

    async def list_blacklists(self, application_id):  # fcg-rewrite
        records = (  # fcg-rewrite
            self.db.query(Blacklist)  # fcg-rewrite
            .filter(Blacklist.application_id == application_id)  # fcg-rewrite
            .order_by(Blacklist.created_at.desc())  # fcg-rewrite
            .all()
        )
        return [  # fcg-rewrite
            BlacklistResponse(  # fcg-rewrite
                id=record.id,  # fcg-rewrite
                name=record.name,  # fcg-rewrite
                keywords=record.keywords or [],  # fcg-rewrite
                description=record.description,  # fcg-rewrite
                is_active=record.is_active,  # fcg-rewrite
                created_at=record.created_at,  # fcg-rewrite
                updated_at=record.updated_at,  # fcg-rewrite
            )
            for record in records  # fcg-rewrite
        ]

    async def create_blacklist(self, tenant, application_id, blacklist_request):  # fcg-rewrite
        blacklist = Blacklist(  # fcg-rewrite
            tenant_id=tenant.id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            name=blacklist_request.name,  # fcg-rewrite
            keywords=blacklist_request.keywords,  # fcg-rewrite
            description=blacklist_request.description,  # fcg-rewrite
            is_active=blacklist_request.is_active,  # fcg-rewrite
        )
        self.db.add(blacklist)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        self.db.refresh(blacklist)  # fcg-rewrite

        await keyword_cache.invalidate_cache()  # fcg-rewrite

        try:
            self._template_service.create_template_for_blacklist(  # fcg-rewrite
                blacklist=blacklist,  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
                tenant_id=tenant.id,  # fcg-rewrite
            )
        except Exception as exc:  # fcg-rewrite
            logger.error("Failed to create response template for blacklist %s: %s", blacklist.name, exc)  # fcg-rewrite

        return blacklist  # fcg-rewrite

    async def update_blacklist(self, application_id, blacklist_id: int, blacklist_request):  # fcg-rewrite
        blacklist = self._load_blacklist(application_id, blacklist_id)  # fcg-rewrite
        blacklist.name = blacklist_request.name  # fcg-rewrite
        blacklist.keywords = blacklist_request.keywords  # fcg-rewrite
        blacklist.description = blacklist_request.description  # fcg-rewrite
        blacklist.is_active = blacklist_request.is_active  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await keyword_cache.invalidate_cache()  # fcg-rewrite
        return blacklist  # fcg-rewrite

    async def delete_blacklist(self, application_id, blacklist_id: int):  # fcg-rewrite
        blacklist = self._load_blacklist(application_id, blacklist_id)  # fcg-rewrite
        blacklist_name = blacklist.name  # fcg-rewrite
        try:
            self._template_service.delete_template_for_blacklist(  # fcg-rewrite
                blacklist_name=blacklist_name,  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
            )
        except Exception as exc:  # fcg-rewrite
            logger.error("Failed to delete response template for blacklist %s: %s", blacklist_name, exc)  # fcg-rewrite

        self.db.delete(blacklist)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await keyword_cache.invalidate_cache()  # fcg-rewrite
        return blacklist  # fcg-rewrite

    async def list_whitelists(self, application_id):  # fcg-rewrite
        records = (  # fcg-rewrite
            self.db.query(Whitelist)  # fcg-rewrite
            .filter(Whitelist.application_id == application_id)  # fcg-rewrite
            .order_by(Whitelist.created_at.desc())  # fcg-rewrite
            .all()
        )
        return [  # fcg-rewrite
            WhitelistResponse(  # fcg-rewrite
                id=record.id,  # fcg-rewrite
                name=record.name,  # fcg-rewrite
                keywords=record.keywords or [],  # fcg-rewrite
                description=record.description,  # fcg-rewrite
                is_active=record.is_active,  # fcg-rewrite
                created_at=record.created_at,  # fcg-rewrite
                updated_at=record.updated_at,  # fcg-rewrite
            )
            for record in records  # fcg-rewrite
        ]

    async def create_whitelist(self, tenant, application_id, whitelist_request):  # fcg-rewrite
        whitelist = Whitelist(  # fcg-rewrite
            tenant_id=tenant.id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            name=whitelist_request.name,  # fcg-rewrite
            keywords=whitelist_request.keywords,  # fcg-rewrite
            description=whitelist_request.description,  # fcg-rewrite
            is_active=whitelist_request.is_active,  # fcg-rewrite
        )
        self.db.add(whitelist)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await keyword_cache.invalidate_cache()  # fcg-rewrite
        return whitelist  # fcg-rewrite

    async def update_whitelist(self, application_id, whitelist_id: int, whitelist_request):  # fcg-rewrite
        whitelist = self._load_whitelist(application_id, whitelist_id)  # fcg-rewrite
        whitelist.name = whitelist_request.name  # fcg-rewrite
        whitelist.keywords = whitelist_request.keywords  # fcg-rewrite
        whitelist.description = whitelist_request.description  # fcg-rewrite
        whitelist.is_active = whitelist_request.is_active  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await keyword_cache.invalidate_cache()  # fcg-rewrite
        return whitelist  # fcg-rewrite

    async def delete_whitelist(self, application_id, whitelist_id: int):  # fcg-rewrite
        whitelist = self._load_whitelist(application_id, whitelist_id)  # fcg-rewrite
        self.db.delete(whitelist)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await keyword_cache.invalidate_cache()  # fcg-rewrite
        return whitelist  # fcg-rewrite

    async def list_response_templates(self, application_id, scanner_type=None, scanner_identifier=None):  # fcg-rewrite
        query = self.db.query(ResponseTemplate).filter(  # fcg-rewrite
            ResponseTemplate.application_id == application_id,  # fcg-rewrite
            ResponseTemplate.is_active == True,  # fcg-rewrite
        )
        if scanner_type:  # fcg-rewrite
            query = query.filter(ResponseTemplate.scanner_type == scanner_type)  # fcg-rewrite
        if scanner_identifier:  # fcg-rewrite
            query = query.filter(ResponseTemplate.scanner_identifier == scanner_identifier)  # fcg-rewrite

        results = query.order_by(ResponseTemplate.created_at.desc()).all()  # fcg-rewrite
        return [  # fcg-rewrite
            ResponseTemplateResponse(  # fcg-rewrite
                id=record.id,  # fcg-rewrite
                tenant_id=str(record.tenant_id) if record.tenant_id else None,  # fcg-rewrite
                application_id=str(record.application_id) if record.application_id else None,  # fcg-rewrite
                category=record.category,  # fcg-rewrite
                scanner_type=record.scanner_type,  # fcg-rewrite
                scanner_identifier=record.scanner_identifier,  # fcg-rewrite
                scanner_name=record.scanner_name,  # fcg-rewrite
                risk_level=record.risk_level,  # fcg-rewrite
                template_content=record.template_content,  # fcg-rewrite
                is_default=record.is_default,  # fcg-rewrite
                is_active=record.is_active,  # fcg-rewrite
                created_at=record.created_at,  # fcg-rewrite
                updated_at=record.updated_at,  # fcg-rewrite
            )
            for record in results  # fcg-rewrite
        ]

    async def create_response_template(self, tenant, application_id, template_request):  # fcg-rewrite
        scanner_name = self._resolve_scanner_name(application_id, template_request.scanner_type, template_request.scanner_identifier)  # fcg-rewrite
        template = ResponseTemplate(  # fcg-rewrite
            tenant_id=tenant.id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            category=template_request.category,  # fcg-rewrite
            scanner_type=template_request.scanner_type,  # fcg-rewrite
            scanner_identifier=template_request.scanner_identifier,  # fcg-rewrite
            scanner_name=scanner_name,  # fcg-rewrite
            risk_level=template_request.risk_level,  # fcg-rewrite
            template_content=template_request.template_content,  # fcg-rewrite
            is_default=template_request.is_default,  # fcg-rewrite
            is_active=template_request.is_active,  # fcg-rewrite
        )
        self.db.add(template)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_template_caches()  # fcg-rewrite
        return template  # fcg-rewrite

    async def update_response_template(self, application_id, template_id: int, template_request):  # fcg-rewrite
        template = self._load_response_template(application_id, template_id)  # fcg-rewrite
        template.category = template_request.category  # fcg-rewrite
        template.scanner_type = template_request.scanner_type  # fcg-rewrite
        template.scanner_identifier = template_request.scanner_identifier  # fcg-rewrite
        template.scanner_name = self._resolve_scanner_name(  # fcg-rewrite
            application_id,  # fcg-rewrite
            template_request.scanner_type,  # fcg-rewrite
            template_request.scanner_identifier,  # fcg-rewrite
        )
        template.risk_level = template_request.risk_level  # fcg-rewrite
        template.template_content = template_request.template_content  # fcg-rewrite
        template.is_default = template_request.is_default  # fcg-rewrite
        template.is_active = template_request.is_active  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_template_caches()  # fcg-rewrite
        return template  # fcg-rewrite

    async def delete_response_template(self, application_id, template_id: int):  # fcg-rewrite
        template = self._load_response_template(application_id, template_id)  # fcg-rewrite
        self.db.delete(template)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_template_caches()  # fcg-rewrite
        return template  # fcg-rewrite

    async def invalidate_template_caches(self):  # fcg-rewrite
        await template_cache.invalidate_cache()  # fcg-rewrite
        await enhanced_template_service.invalidate_cache()  # fcg-rewrite

    def _load_blacklist(self, application_id, blacklist_id: int):  # fcg-rewrite
        blacklist = self.db.query(Blacklist).filter_by(id=blacklist_id, application_id=application_id).first()  # fcg-rewrite
        if not blacklist:  # fcg-rewrite
            raise ValueError("Blacklist not found")  # fcg-rewrite
        return blacklist  # fcg-rewrite

    def _load_whitelist(self, application_id, whitelist_id: int):  # fcg-rewrite
        whitelist = self.db.query(Whitelist).filter_by(id=whitelist_id, application_id=application_id).first()  # fcg-rewrite
        if not whitelist:  # fcg-rewrite
            raise ValueError("Whitelist not found")  # fcg-rewrite
        return whitelist  # fcg-rewrite

    def _load_response_template(self, application_id, template_id: int):  # fcg-rewrite
        template = self.db.query(ResponseTemplate).filter_by(id=template_id, application_id=application_id).first()  # fcg-rewrite
        if not template:  # fcg-rewrite
            raise ValueError("Response template not found")  # fcg-rewrite
        return template  # fcg-rewrite

    def _resolve_scanner_name(self, application_id, scanner_type, scanner_identifier):  # fcg-rewrite
        if not scanner_type or not scanner_identifier:  # fcg-rewrite
            return None  # fcg-rewrite

        if scanner_type == "blacklist":  # fcg-rewrite
            blacklist = self.db.query(Blacklist).filter(  # fcg-rewrite
                Blacklist.application_id == application_id,  # fcg-rewrite
                Blacklist.name == scanner_identifier,  # fcg-rewrite
            ).first()  # fcg-rewrite
            return blacklist.name if blacklist else None  # fcg-rewrite

        if scanner_type == "whitelist":  # fcg-rewrite
            whitelist = self.db.query(Whitelist).filter(  # fcg-rewrite
                Whitelist.application_id == application_id,  # fcg-rewrite
                Whitelist.name == scanner_identifier,  # fcg-rewrite
            ).first()  # fcg-rewrite
            return whitelist.name if whitelist else None  # fcg-rewrite

        if scanner_type in ["official_scanner", "marketplace_scanner", "custom_scanner"]:  # fcg-rewrite
            scanner = self.db.query(Scanner).filter(Scanner.tag == scanner_identifier).first()  # fcg-rewrite
            return scanner.name if scanner else None  # fcg-rewrite

        return None  # fcg-rewrite
