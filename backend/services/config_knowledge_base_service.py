"""Knowledge-base configuration flows extracted from config_api."""

from fastapi import HTTPException  # fcg-rewrite

from database.models import (  # fcg-rewrite
    ApplicationSettings,  # fcg-rewrite
    Blacklist,  # fcg-rewrite
    CustomScanner,  # fcg-rewrite
    KnowledgeBase,  # fcg-rewrite
    PackagePurchase,  # fcg-rewrite
    Scanner,  # fcg-rewrite
    ScannerPackage,  # fcg-rewrite
    TenantKnowledgeBaseDisable,  # fcg-rewrite
    Whitelist,  # fcg-rewrite
)
from models.responses import KnowledgeBaseFileInfo, KnowledgeBaseResponse, SimilarQuestionResult  # fcg-rewrite
from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite
from services.knowledge_base_service import knowledge_base_service  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


class ConfigKnowledgeBaseService:  # fcg-rewrite
    """Own knowledge-base registry and file lifecycle flows."""

    VALID_SCANNER_TYPES = ["blacklist", "whitelist", "official_scanner", "marketplace_scanner", "custom_scanner"]  # fcg-rewrite
    VALID_CATEGORIES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "S11", "S12"]  # fcg-rewrite

    def __init__(self, db) -> None:  # fcg-rewrite
        self.db = db  # fcg-rewrite

    async def list_knowledge_bases(self, tenant, application_id, category=None):  # fcg-rewrite
        query = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
            (KnowledgeBase.application_id == application_id) | (KnowledgeBase.is_global == True)  # fcg-rewrite
        )
        if category:  # fcg-rewrite
            query = query.filter(KnowledgeBase.category == category)  # fcg-rewrite

        knowledge_bases = query.order_by(KnowledgeBase.created_at.desc()).all()  # fcg-rewrite
        disabled_kb_ids = set(  # fcg-rewrite
            disable.kb_id  # fcg-rewrite
            for disable in self.db.query(TenantKnowledgeBaseDisable).filter(  # fcg-rewrite
                TenantKnowledgeBaseDisable.tenant_id == tenant.id  # fcg-rewrite
            ).all()
        )
        return [self._serialize_knowledge_base(record, include_disable_flag=True, disabled_kb_ids=disabled_kb_ids) for record in knowledge_bases]  # fcg-rewrite

    async def create_knowledge_base(  # fcg-rewrite
        self,
        tenant,
        application_id,  # fcg-rewrite
        *,
        file_content: bytes,  # fcg-rewrite
        original_filename: str,  # fcg-rewrite
        category=None,  # fcg-rewrite
        scanner_type=None,  # fcg-rewrite
        scanner_identifier=None,  # fcg-rewrite
        name: str,  # fcg-rewrite
        description: str,  # fcg-rewrite
        similarity_threshold: float,  # fcg-rewrite
        is_active: bool,  # fcg-rewrite
        is_global: bool,  # fcg-rewrite
    ):
        scanner_type, scanner_identifier = self._normalize_scanner_target(category, scanner_type, scanner_identifier)  # fcg-rewrite
        self._validate_similarity_threshold(similarity_threshold)  # fcg-rewrite
        self._ensure_global_permission(tenant, is_global)  # fcg-rewrite
        scanner_name = self._resolve_scanner_name(application_id, scanner_type, scanner_identifier)  # fcg-rewrite
        self._ensure_unique_scanner_knowledge_base(application_id, scanner_type, scanner_identifier, name, is_global)  # fcg-rewrite

        qa_pairs = knowledge_base_service.parse_jsonl_file(file_content)  # fcg-rewrite
        knowledge_base = KnowledgeBase(  # fcg-rewrite
            tenant_id=tenant.id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            category=category,  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            scanner_identifier=scanner_identifier,  # fcg-rewrite
            scanner_name=scanner_name,  # fcg-rewrite
            name=name,  # fcg-rewrite
            description=description,  # fcg-rewrite
            file_path="",  # fcg-rewrite
            total_qa_pairs=len(qa_pairs),  # fcg-rewrite
            similarity_threshold=similarity_threshold,  # fcg-rewrite
            is_active=is_active,  # fcg-rewrite
            is_global=is_global,  # fcg-rewrite
        )
        self.db.add(knowledge_base)  # fcg-rewrite
        self.db.flush()  # fcg-rewrite

        file_path = knowledge_base_service.save_original_file(file_content, knowledge_base.id, original_filename)  # fcg-rewrite
        knowledge_base.file_path = file_path  # fcg-rewrite
        knowledge_base.vector_file_path = knowledge_base_service.create_vector_index(qa_pairs, knowledge_base.id)  # fcg-rewrite

        self.db.commit()  # fcg-rewrite
        await self.invalidate_kb_cache()  # fcg-rewrite
        return knowledge_base  # fcg-rewrite

    async def get_available_scanners(self, tenant, application_id):  # fcg-rewrite
        result = {  # fcg-rewrite
            "blacklists": [],  # fcg-rewrite
            "whitelists": [],  # fcg-rewrite
            "official_scanners": [],  # fcg-rewrite
            "marketplace_scanners": [],  # fcg-rewrite
            "custom_scanners": [],  # fcg-rewrite
        }

        blacklists = self.db.query(Blacklist).filter(  # fcg-rewrite
            Blacklist.application_id == application_id,  # fcg-rewrite
            Blacklist.is_active == True,  # fcg-rewrite
        ).all()
        result["blacklists"] = [{"value": item.name, "label": f"Blacklist - {item.name}"} for item in blacklists]  # fcg-rewrite

        whitelists = self.db.query(Whitelist).filter(  # fcg-rewrite
            Whitelist.application_id == application_id,  # fcg-rewrite
            Whitelist.is_active == True,  # fcg-rewrite
        ).all()
        result["whitelists"] = [{"value": item.name, "label": f"Whitelist - {item.name}"} for item in whitelists]  # fcg-rewrite

        official_scanners = self.db.query(Scanner).join(  # fcg-rewrite
            ScannerPackage, Scanner.package_id == ScannerPackage.id  # fcg-rewrite
        ).filter(  # fcg-rewrite
            ScannerPackage.is_official == True,  # fcg-rewrite
            ScannerPackage.package_type == "basic",  # fcg-rewrite
        ).order_by(Scanner.tag).all()  # fcg-rewrite
        result["official_scanners"] = [{"value": item.tag, "label": f"{item.tag} - {item.name}"} for item in official_scanners]  # fcg-rewrite

        marketplace_scanners = []  # fcg-rewrite
        if getattr(tenant, "is_super_admin", False):  # fcg-rewrite
            marketplace_scanners = self.db.query(Scanner).join(  # fcg-rewrite
                ScannerPackage, Scanner.package_id == ScannerPackage.id  # fcg-rewrite
            ).filter(  # fcg-rewrite
                ScannerPackage.package_type == "purchasable",  # fcg-rewrite
                Scanner.is_active == True,  # fcg-rewrite
            ).order_by(Scanner.tag).all()  # fcg-rewrite
        else:
            approved_package_ids = [  # fcg-rewrite
                row[0]
                for row in self.db.query(PackagePurchase.package_id).filter(  # fcg-rewrite
                    PackagePurchase.tenant_id == tenant.id,  # fcg-rewrite
                    PackagePurchase.status == "approved",  # fcg-rewrite
                ).all()
            ]
            if approved_package_ids:  # fcg-rewrite
                marketplace_scanners = self.db.query(Scanner).join(  # fcg-rewrite
                    ScannerPackage, Scanner.package_id == ScannerPackage.id  # fcg-rewrite
                ).filter(  # fcg-rewrite
                    ScannerPackage.package_type == "purchasable",  # fcg-rewrite
                    Scanner.package_id.in_(approved_package_ids),  # fcg-rewrite
                    Scanner.is_active == True,  # fcg-rewrite
                ).order_by(Scanner.tag).all()  # fcg-rewrite
        result["marketplace_scanners"] = [{"value": item.tag, "label": f"{item.tag} - {item.name}"} for item in marketplace_scanners]  # fcg-rewrite

        custom_scanners = self.db.query(Scanner).join(  # fcg-rewrite
            CustomScanner, CustomScanner.scanner_id == Scanner.id  # fcg-rewrite
        ).filter(  # fcg-rewrite
            CustomScanner.application_id == application_id,  # fcg-rewrite
            Scanner.is_active == True,  # fcg-rewrite
        ).order_by(Scanner.tag).all()  # fcg-rewrite
        result["custom_scanners"] = [{"value": item.tag, "label": f"{item.tag} - {item.name}"} for item in custom_scanners]  # fcg-rewrite
        return result  # fcg-rewrite

    async def update_knowledge_base(self, tenant, application_id, kb_id: int, kb_request):  # fcg-rewrite
        knowledge_base = self._load_knowledge_base(kb_id)  # fcg-rewrite
        if knowledge_base.application_id != application_id and not (getattr(tenant, "is_super_admin", False) and knowledge_base.is_global):  # fcg-rewrite
            raise HTTPException(status_code=403, detail="Permission denied")  # fcg-rewrite
        self._ensure_global_permission(tenant, kb_request.is_global)  # fcg-rewrite
        self._ensure_unique_category_knowledge_base(application_id, kb_request.category, kb_request.name, kb_id, kb_request.is_global)  # fcg-rewrite

        knowledge_base.category = kb_request.category  # fcg-rewrite
        knowledge_base.name = kb_request.name  # fcg-rewrite
        knowledge_base.description = kb_request.description  # fcg-rewrite
        knowledge_base.similarity_threshold = kb_request.similarity_threshold  # fcg-rewrite
        knowledge_base.is_active = kb_request.is_active  # fcg-rewrite
        knowledge_base.is_global = kb_request.is_global  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_kb_cache()  # fcg-rewrite
        return knowledge_base  # fcg-rewrite

    async def delete_knowledge_base(self, tenant, application_id, kb_id: int):  # fcg-rewrite
        knowledge_base = self._load_knowledge_base(kb_id)  # fcg-rewrite
        if knowledge_base.application_id != application_id and not (getattr(tenant, "is_super_admin", False) and knowledge_base.is_global):  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=403,  # fcg-rewrite
                detail="Permission denied. You can only delete your own knowledge bases, or administrators can delete system-level knowledge bases.",  # fcg-rewrite
            )
        knowledge_base_service.delete_knowledge_base_files(kb_id)  # fcg-rewrite
        self.db.delete(knowledge_base)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_kb_cache()  # fcg-rewrite
        return knowledge_base  # fcg-rewrite

    async def replace_knowledge_base_file(self, application_id, kb_id: int, file_content: bytes, filename: str):  # fcg-rewrite
        knowledge_base = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
            KnowledgeBase.id == kb_id,  # fcg-rewrite
            KnowledgeBase.application_id == application_id,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not knowledge_base:  # fcg-rewrite
            raise HTTPException(status_code=404, detail="Knowledge base not found")  # fcg-rewrite

        qa_pairs = knowledge_base_service.parse_jsonl_file(file_content)  # fcg-rewrite
        knowledge_base_service.delete_knowledge_base_files(kb_id)  # fcg-rewrite
        knowledge_base.file_path = knowledge_base_service.save_original_file(file_content, kb_id, filename)  # fcg-rewrite
        knowledge_base.vector_file_path = knowledge_base_service.create_vector_index(qa_pairs, kb_id)  # fcg-rewrite
        knowledge_base.total_qa_pairs = len(qa_pairs)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_kb_cache()  # fcg-rewrite
        return knowledge_base  # fcg-rewrite

    async def get_knowledge_base_info(self, application_id, kb_id: int):  # fcg-rewrite
        knowledge_base = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
            KnowledgeBase.id == kb_id,  # fcg-rewrite
            ((KnowledgeBase.application_id == application_id) | (KnowledgeBase.is_global == True)),  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not knowledge_base:  # fcg-rewrite
            raise HTTPException(status_code=404, detail="Knowledge base not found")  # fcg-rewrite
        return KnowledgeBaseFileInfo(**knowledge_base_service.get_file_info(kb_id))  # fcg-rewrite

    async def search_similar_questions(self, application_id, kb_id: int, query: str, top_k: int):  # fcg-rewrite
        knowledge_base = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
            KnowledgeBase.id == kb_id,  # fcg-rewrite
            ((KnowledgeBase.application_id == application_id) | (KnowledgeBase.is_global == True)),  # fcg-rewrite
            KnowledgeBase.is_active == True,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not knowledge_base:  # fcg-rewrite
            raise HTTPException(status_code=404, detail="Knowledge base not found or not active")  # fcg-rewrite
        if not query.strip():  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Query cannot be empty")  # fcg-rewrite

        results = knowledge_base_service.search_similar_questions(  # fcg-rewrite
            query.strip(),  # fcg-rewrite
            kb_id,
            top_k,
            similarity_threshold=knowledge_base.similarity_threshold,  # fcg-rewrite
            db=self.db,  # fcg-rewrite
        )
        return [SimilarQuestionResult(**result) for result in results]  # fcg-rewrite

    async def list_knowledge_bases_by_category(self, application_id, category: str):  # fcg-rewrite
        if category not in self.VALID_CATEGORIES:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Invalid category")  # fcg-rewrite
        knowledge_bases = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
            ((KnowledgeBase.application_id == application_id) | (KnowledgeBase.is_global == True)),  # fcg-rewrite
            KnowledgeBase.category == category,  # fcg-rewrite
            KnowledgeBase.is_active == True,  # fcg-rewrite
        ).order_by(KnowledgeBase.created_at.desc()).all()  # fcg-rewrite
        return [self._serialize_knowledge_base(record, include_disable_flag=False) for record in knowledge_bases]  # fcg-rewrite

    async def toggle_global_knowledge_base_disable(self, tenant, kb_id: int):  # fcg-rewrite
        knowledge_base = self._load_knowledge_base(kb_id)  # fcg-rewrite
        if not knowledge_base.is_global:  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=400,  # fcg-rewrite
                detail="Only global knowledge bases can be toggled via this endpoint. Use update API for your own knowledge bases.",  # fcg-rewrite
            )

        existing_disable = self.db.query(TenantKnowledgeBaseDisable).filter(  # fcg-rewrite
            TenantKnowledgeBaseDisable.tenant_id == tenant.id,  # fcg-rewrite
            TenantKnowledgeBaseDisable.kb_id == kb_id,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if existing_disable:  # fcg-rewrite
            self.db.delete(existing_disable)  # fcg-rewrite
            self.db.commit()  # fcg-rewrite
            await self.invalidate_kb_cache()  # fcg-rewrite
            return False  # fcg-rewrite

        disable_record = TenantKnowledgeBaseDisable(tenant_id=tenant.id, kb_id=kb_id)  # fcg-rewrite
        self.db.add(disable_record)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        await self.invalidate_kb_cache()  # fcg-rewrite
        return True  # fcg-rewrite

    async def check_global_knowledge_base_disabled(self, tenant, kb_id: int):  # fcg-rewrite
        knowledge_base = self._load_knowledge_base(kb_id)  # fcg-rewrite
        is_disabled = self.db.query(TenantKnowledgeBaseDisable).filter(  # fcg-rewrite
            TenantKnowledgeBaseDisable.tenant_id == tenant.id,  # fcg-rewrite
            TenantKnowledgeBaseDisable.kb_id == kb_id,  # fcg-rewrite
        ).first() is not None  # fcg-rewrite
        return {"kb_id": kb_id, "is_global": knowledge_base.is_global, "is_disabled": is_disabled}  # fcg-rewrite

    async def invalidate_kb_cache(self):  # fcg-rewrite
        await enhanced_template_service.invalidate_cache()  # fcg-rewrite

    def _load_knowledge_base(self, kb_id: int):  # fcg-rewrite
        knowledge_base = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()  # fcg-rewrite
        if not knowledge_base:  # fcg-rewrite
            raise HTTPException(status_code=404, detail="Knowledge base not found")  # fcg-rewrite
        return knowledge_base  # fcg-rewrite

    def _normalize_scanner_target(self, category, scanner_type, scanner_identifier):  # fcg-rewrite
        if scanner_type and scanner_identifier:  # fcg-rewrite
            resolved_type = scanner_type  # fcg-rewrite
            resolved_identifier = scanner_identifier  # fcg-rewrite
        elif category:  # fcg-rewrite
            resolved_type = "official_scanner"  # fcg-rewrite
            resolved_identifier = category  # fcg-rewrite
        else:
            raise HTTPException(status_code=400, detail="Either category OR (scanner_type + scanner_identifier) is required")  # fcg-rewrite

        if resolved_type not in self.VALID_SCANNER_TYPES:  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=400,  # fcg-rewrite
                detail=f"Invalid scanner_type. Must be one of: {', '.join(self.VALID_SCANNER_TYPES)}",  # fcg-rewrite
            )
        return resolved_type, resolved_identifier  # fcg-rewrite

    def _validate_similarity_threshold(self, similarity_threshold: float):  # fcg-rewrite
        if similarity_threshold < 0 or similarity_threshold > 1:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="similarity_threshold must be between 0 and 1")  # fcg-rewrite

    def _ensure_global_permission(self, tenant, is_global: bool):  # fcg-rewrite
        if is_global and not getattr(tenant, "is_super_admin", False):  # fcg-rewrite
            raise HTTPException(status_code=403, detail="Only administrators can create global knowledge bases")  # fcg-rewrite

    def _resolve_scanner_name(self, application_id, scanner_type, scanner_identifier):  # fcg-rewrite
        if scanner_type == "blacklist":  # fcg-rewrite
            blacklist = self.db.query(Blacklist).filter(  # fcg-rewrite
                Blacklist.application_id == application_id,  # fcg-rewrite
                Blacklist.name == scanner_identifier,  # fcg-rewrite
            ).first()  # fcg-rewrite
            if not blacklist:  # fcg-rewrite
                raise HTTPException(status_code=404, detail=f"Blacklist '{scanner_identifier}' not found")  # fcg-rewrite
            return blacklist.name  # fcg-rewrite

        if scanner_type == "whitelist":  # fcg-rewrite
            whitelist = self.db.query(Whitelist).filter(  # fcg-rewrite
                Whitelist.application_id == application_id,  # fcg-rewrite
                Whitelist.name == scanner_identifier,  # fcg-rewrite
            ).first()  # fcg-rewrite
            if not whitelist:  # fcg-rewrite
                raise HTTPException(status_code=404, detail=f"Whitelist '{scanner_identifier}' not found")  # fcg-rewrite
            return whitelist.name  # fcg-rewrite

        if scanner_type == "official_scanner":  # fcg-rewrite
            scanner = self.db.query(Scanner).filter(Scanner.tag == scanner_identifier).first()  # fcg-rewrite
            if not scanner:  # fcg-rewrite
                raise HTTPException(status_code=404, detail=f"Official scanner '{scanner_identifier}' not found")  # fcg-rewrite
            return scanner.name  # fcg-rewrite

        if scanner_type == "marketplace_scanner":  # fcg-rewrite
            scanner = self.db.query(Scanner).filter(Scanner.tag == scanner_identifier).first()  # fcg-rewrite
            if not scanner:  # fcg-rewrite
                raise HTTPException(status_code=404, detail=f"Marketplace scanner '{scanner_identifier}' not found")  # fcg-rewrite
            return scanner.name  # fcg-rewrite

        custom_scanner = self.db.query(CustomScanner).join(Scanner).filter(  # fcg-rewrite
            CustomScanner.application_id == application_id,  # fcg-rewrite
            Scanner.tag == scanner_identifier,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not custom_scanner:  # fcg-rewrite
            raise HTTPException(status_code=404, detail=f"Custom scanner '{scanner_identifier}' not found")  # fcg-rewrite
        return custom_scanner.scanner.name  # fcg-rewrite

    def _ensure_unique_scanner_knowledge_base(self, application_id, scanner_type, scanner_identifier, name, is_global: bool):  # fcg-rewrite
        if is_global:  # fcg-rewrite
            existing = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
                KnowledgeBase.is_global == True,  # fcg-rewrite
                KnowledgeBase.scanner_type == scanner_type,  # fcg-rewrite
                KnowledgeBase.scanner_identifier == scanner_identifier,  # fcg-rewrite
                KnowledgeBase.name == name,  # fcg-rewrite
            ).first()  # fcg-rewrite
        else:
            existing = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
                KnowledgeBase.application_id == application_id,  # fcg-rewrite
                KnowledgeBase.scanner_type == scanner_type,  # fcg-rewrite
                KnowledgeBase.scanner_identifier == scanner_identifier,  # fcg-rewrite
                KnowledgeBase.name == name,  # fcg-rewrite
            ).first()  # fcg-rewrite
        if existing:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Knowledge base with this name already exists for this scanner")  # fcg-rewrite

    def _ensure_unique_category_knowledge_base(self, application_id, category, name, kb_id: int, is_global: bool):  # fcg-rewrite
        if is_global:  # fcg-rewrite
            existing = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
                KnowledgeBase.is_global == True,  # fcg-rewrite
                KnowledgeBase.category == category,  # fcg-rewrite
                KnowledgeBase.name == name,  # fcg-rewrite
                KnowledgeBase.id != kb_id,  # fcg-rewrite
            ).first()  # fcg-rewrite
        else:
            existing = self.db.query(KnowledgeBase).filter(  # fcg-rewrite
                KnowledgeBase.application_id == application_id,  # fcg-rewrite
                KnowledgeBase.category == category,  # fcg-rewrite
                KnowledgeBase.name == name,  # fcg-rewrite
                KnowledgeBase.id != kb_id,  # fcg-rewrite
            ).first()  # fcg-rewrite
        if existing:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Knowledge base with this name already exists for this category")  # fcg-rewrite

    def _serialize_knowledge_base(self, knowledge_base, *, include_disable_flag: bool, disabled_kb_ids=None):  # fcg-rewrite
        return KnowledgeBaseResponse(  # fcg-rewrite
            id=knowledge_base.id,  # fcg-rewrite
            category=knowledge_base.category,  # fcg-rewrite
            scanner_type=knowledge_base.scanner_type,  # fcg-rewrite
            scanner_identifier=knowledge_base.scanner_identifier,  # fcg-rewrite
            scanner_name=knowledge_base.scanner_name,  # fcg-rewrite
            name=knowledge_base.name,  # fcg-rewrite
            description=knowledge_base.description,  # fcg-rewrite
            file_path=knowledge_base.file_path,  # fcg-rewrite
            vector_file_path=knowledge_base.vector_file_path,  # fcg-rewrite
            total_qa_pairs=knowledge_base.total_qa_pairs,  # fcg-rewrite
            similarity_threshold=knowledge_base.similarity_threshold,  # fcg-rewrite
            is_active=knowledge_base.is_active,  # fcg-rewrite
            is_global=knowledge_base.is_global,  # fcg-rewrite
            is_disabled_by_me=knowledge_base.id in (disabled_kb_ids or set()) if include_disable_flag and knowledge_base.is_global else False,  # fcg-rewrite
            created_at=knowledge_base.created_at,  # fcg-rewrite
            updated_at=knowledge_base.updated_at,  # fcg-rewrite
        )
