from typing import List, Optional

from database.connection import get_db_session
from services.knowledge_base_service import knowledge_base_service
from utils.logger import setup_logger

logger = setup_logger()


class EnhancedTemplateKnowledgeMatcher:
    """Knowledge-base lookup helpers for enhanced template answers."""

    CATEGORY_MAPPING = {
        "General Political Topics": "S1",
        "Sensitive Political Topics": "S2",
        "Insult to National Symbols or Leaders": "S3",
        "Harm to Minors": "S4",
        "Violent Crime": "S5",
        "Non-Violent Crime": "S6",
        "Pornography": "S7",
        "Hate & Discrimination": "S8",
        "Prompt Attacks": "S9",
        "Profanity": "S10",
        "Privacy Invasion": "S11",
        "Commercial Violations": "S12",
        "Intellectual Property Infringement": "S13",
        "Harassment": "S14",
        "Weapons of Mass Destruction": "S15",
        "Self-Harm": "S16",
        "Sexual Crimes": "S17",
        "Threats": "S18",
        "Professional Financial Advice": "S19",
        "Professional Medical Advice": "S20",
        "Professional Legal Advice": "S21",
    }

    def __init__(self, cache_store):
        self.cache_store = cache_store

    async def search_knowledge_base(
        self,
        user_query: str,
        tenant_id: Optional[str],
        application_id: str,
        scanner_type: Optional[str],
        scanner_identifier: Optional[str],
        categories: List[str],
    ) -> Optional[str]:
        try:
            if scanner_type and scanner_identifier:
                scanner_key = f"{scanner_type}:{scanner_identifier}"
                kb_ids = self.cache_store.get_kb_ids_for_key(application_id, scanner_key, tenant_id)
                if kb_ids:
                    result = await self.search_kb_ids(kb_ids, user_query)
                    if result:
                        return result

            for category in categories:
                category_key = self.get_category_key(category)
                if not category_key:
                    continue
                kb_ids = self.cache_store.get_kb_ids_for_key(application_id, category_key, tenant_id)
                if kb_ids:
                    result = await self.search_kb_ids(kb_ids, user_query)
                    if result:
                        return result

            return None
        except Exception as exc:
            logger.error(f"Knowledge base search error: {exc}", exc_info=True)
            return None

    async def search_kb_ids(self, kb_ids: List[int], user_query: str) -> Optional[str]:
        db = get_db_session()
        try:
            for kb_id in kb_ids:
                try:
                    results = knowledge_base_service.search_similar_questions(
                        user_query, kb_id, top_k=1, db=db
                    )
                    if results:
                        logger.info(
                            f"KB {kb_id} hit with similarity: {results[0]['similarity_score']:.3f}"
                        )
                        return results[0]["answer"]
                except Exception as exc:
                    logger.warning(f"Error searching KB {kb_id}: {exc}")
                    continue
            return None
        finally:
            db.close()

    def get_category_key(self, category: str) -> Optional[str]:
        return self.CATEGORY_MAPPING.get(category)
