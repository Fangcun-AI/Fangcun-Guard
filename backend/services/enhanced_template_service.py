"""
Enhanced Template Service

Provides intelligent answer generation for blocked content:
1. Proxy Answer (代答): When knowledge base is hit, generate safe response using guardrail model
2. Fixed Answer (据答): When no KB hit, use generic template with scanner_name

Flow:
  User Query → Risk Detected → Search Knowledge Base
                                    ↓
                           ┌───────┴───────┐
                           ↓               ↓
                      KB Hit           KB Miss
                           ↓               ↓
                  Generate Proxy    Return Fixed
                  Answer (Model)    Answer (Template)
                           ↓               ↓
                      Safe Response   Template Response
"""
from typing import Optional, List  # fcg-rewrite
from services.enhanced_template_cache import EnhancedTemplateCache  # fcg-rewrite
from services.enhanced_template_kb_matcher import EnhancedTemplateKnowledgeMatcher  # fcg-rewrite
from services.proxy_answer_service import proxy_answer_service  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

# Default templates (same as in config_api.py)
DEFAULT_TEMPLATES = {  # fcg-rewrite
    "security_risk_template": {  # fcg-rewrite
        "en": "Request blocked by FangcunGuard.\n\nTriggered rule: {scanner_name}\nDetails: {match_details}",  # fcg-rewrite
        "zh": "请求已被 FangcunGuard 拦截。\n\n触发规则：{scanner_name}\n检测详情：{match_details}"  # fcg-rewrite
    },
    "data_leakage_template": {  # fcg-rewrite
        "en": "Request blocked by FangcunGuard due to possible sensitive data ({entity_type_names}).",  # fcg-rewrite
        "zh": "请求已被 FangcunGuard 拦截，原因：检测到敏感数据（{entity_type_names}）。"  # fcg-rewrite
    }
}

logger = setup_logger()  # fcg-rewrite


class TemplateEngine:  # fcg-rewrite
    """Enhanced template service with proxy answer generation"""

    def __init__(self, cache_ttl: int = 600):  # fcg-rewrite
        self.cache_store = EnhancedTemplateCache(cache_ttl=cache_ttl)  # fcg-rewrite
        self.kb_matcher = EnhancedTemplateKnowledgeMatcher(self.cache_store)  # fcg-rewrite

    async def get_suggest_answer(  # fcg-rewrite
        self,
        categories: List[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        user_language: Optional[str] = None,  # fcg-rewrite
        scanner_type: Optional[str] = None,  # fcg-rewrite
        scanner_identifier: Optional[str] = None,  # fcg-rewrite
        scanner_name: Optional[str] = None,  # fcg-rewrite
        match_details: Optional[str] = None  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        """
        Get suggested answer - proxy answer (代答) or fixed answer (据答).

        Flow:
        1. If user_query provided, search knowledge base
        2. If KB hit, generate proxy answer using guardrail model
        3. If KB miss or no user_query, return fixed answer template

        Args:
            categories: Risk categories list
            tenant_id: Tenant ID
            application_id: Application ID
            user_query: User's original question (for KB search and proxy answer)
            user_language: User's preferred language ('en', 'zh')
            scanner_type: Scanner type
            scanner_identifier: Scanner identifier (e.g., S8, S100)
            scanner_name: Human-readable scanner name

        Returns:
            Suggested answer (proxy or fixed)
        """
        await self.cache_store.ensure_fresh()  # fcg-rewrite

        lang = user_language or 'en'  # fcg-rewrite

        # If no scanner_name provided, try to extract from categories
        if not scanner_name and categories:  # fcg-rewrite
            scanner_name = categories[0]  # fcg-rewrite

        # If no scanner_name still, use default
        if not scanner_name:  # fcg-rewrite
            scanner_name = "policy violation" if lang != 'zh' else "政策违规"  # fcg-rewrite

        # Try proxy answer (代答) if user_query is provided
        if user_query and user_query.strip() and application_id:  # fcg-rewrite
            try:
                kb_answer = await self._search_and_generate_proxy_answer(  # fcg-rewrite
                    user_query=user_query.strip(),  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    application_id=application_id,  # fcg-rewrite
                    scanner_type=scanner_type,  # fcg-rewrite
                    scanner_identifier=scanner_identifier,  # fcg-rewrite
                    scanner_name=scanner_name,  # fcg-rewrite
                    categories=categories,  # fcg-rewrite
                    user_language=lang  # fcg-rewrite
                )
                if kb_answer:  # fcg-rewrite
                    return kb_answer  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"Proxy answer generation failed: {e}", exc_info=True)  # fcg-rewrite

        # Try contextual rejection (no KB needed) — ask guardrail model to
        # generate an analytical response that explains WHY the request was blocked
        if user_query and user_query.strip():  # fcg-rewrite
            try:
                contextual = await self._generate_contextual_rejection(  # fcg-rewrite
                    user_query=user_query.strip(),  # fcg-rewrite
                    scanner_name=scanner_name,  # fcg-rewrite
                    match_details=match_details,  # fcg-rewrite
                    user_language=lang  # fcg-rewrite
                )
                if contextual:  # fcg-rewrite
                    return contextual  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"Contextual rejection generation failed: {e}", exc_info=True)  # fcg-rewrite

        # Fallback to fixed answer (据答)
        return self._get_fixed_answer(scanner_name, lang, application_id,  # fcg-rewrite
                                      scanner_type=scanner_type,  # fcg-rewrite
                                      scanner_identifier=scanner_identifier,  # fcg-rewrite
                                      match_details=match_details)  # fcg-rewrite

    async def _generate_contextual_rejection(  # fcg-rewrite
        self,
        user_query: str,  # fcg-rewrite
        scanner_name: str,  # fcg-rewrite
        match_details: Optional[str],  # fcg-rewrite
        user_language: str  # fcg-rewrite
    ) -> Optional[str]:  # fcg-rewrite
        """Generate a contextual rejection that analyzes the user's request
        and explains why it was blocked, without needing a knowledge base hit."""
        try:
            details_text = f"\n检测详情：{match_details}" if match_details else ""  # fcg-rewrite
            if user_language == 'zh':  # fcg-rewrite
                system_prompt = f"""你是 FangcunGuard 安全系统。用户的请求触发了安全规则「{scanner_name}」。{details_text}  # fcg-rewrite

你的任务：
1. 简要说明你理解用户想做什么
2. 具体指出请求中哪些内容触发了安全规则，以及为什么这些内容有风险
3. 给出建设性的替代建议（如何修改请求以避免触发规则）

要求：
- 回复要专业、有分析性，不要笼统地说"违反了策略"
- 不要生成用户要求的危险内容
- 控制在 150 字以内"""
            else:
                system_prompt = f"""You are FangcunGuard security system. The user's request triggered rule "{scanner_name}".{details_text}  # fcg-rewrite

Your task:
1. Briefly acknowledge what the user is trying to do
2. Specifically point out which parts triggered the rule and why
3. Suggest constructive alternatives

Requirements:
- Be analytical and specific, not vague
- Do NOT generate the dangerous content requested
- Keep response under 150 words"""

            messages = [  # fcg-rewrite
                {"role": "system", "content": system_prompt},  # fcg-rewrite
                {"role": "user", "content": user_query}  # fcg-rewrite
            ]

            answer = await proxy_answer_service._call_model(messages)  # fcg-rewrite
            return answer  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            logger.error(f"Contextual rejection failed: {e}", exc_info=True)  # fcg-rewrite
            return None  # fcg-rewrite

    async def _search_and_generate_proxy_answer(  # fcg-rewrite
        self,
        user_query: str,  # fcg-rewrite
        tenant_id: Optional[str],  # fcg-rewrite
        application_id: str,  # fcg-rewrite
        scanner_type: Optional[str],  # fcg-rewrite
        scanner_identifier: Optional[str],  # fcg-rewrite
        scanner_name: str,  # fcg-rewrite
        categories: List[str],  # fcg-rewrite
        user_language: str  # fcg-rewrite
    ) -> Optional[str]:  # fcg-rewrite
        """
        Search knowledge base and generate proxy answer if hit.

        Args:
            user_query: User's original question
            tenant_id: Tenant ID
            application_id: Application ID
            scanner_type: Scanner type
            scanner_identifier: Scanner identifier
            scanner_name: Human-readable scanner name
            categories: Risk categories
            user_language: User's preferred language

        Returns:
            Generated proxy answer or None if no KB hit
        """
        # Search knowledge base
        kb_content = await self._search_knowledge_base(  # fcg-rewrite
            user_query=user_query,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            scanner_identifier=scanner_identifier,  # fcg-rewrite
            categories=categories  # fcg-rewrite
        )

        if not kb_content:  # fcg-rewrite
            logger.debug(f"No KB hit for query: {user_query[:50]}...")  # fcg-rewrite
            return None  # fcg-rewrite

        # Generate proxy answer using guardrail model
        logger.info(f"KB hit, generating proxy answer for scanner: {scanner_name}")  # fcg-rewrite

        proxy_answer = await proxy_answer_service.generate_proxy_answer(  # fcg-rewrite
            user_query=user_query,  # fcg-rewrite
            kb_reference=kb_content,  # fcg-rewrite
            scanner_name=scanner_name,  # fcg-rewrite
            risk_level="medium_risk",  # Could be passed from caller  # fcg-rewrite
            user_language=user_language  # fcg-rewrite
        )

        return proxy_answer  # fcg-rewrite

    async def _search_knowledge_base(  # fcg-rewrite
        self,
        user_query: str,  # fcg-rewrite
        tenant_id: Optional[str],  # fcg-rewrite
        application_id: str,  # fcg-rewrite
        scanner_type: Optional[str],  # fcg-rewrite
        scanner_identifier: Optional[str],  # fcg-rewrite
        categories: List[str]  # fcg-rewrite
    ) -> Optional[str]:  # fcg-rewrite
        """
        Search knowledge base for similar content.

        Returns:
            KB answer content if found, None otherwise
        """
        return await self.kb_matcher.search_knowledge_base(  # fcg-rewrite
            user_query,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
            scanner_type,  # fcg-rewrite
            scanner_identifier,  # fcg-rewrite
            categories,  # fcg-rewrite
        )

    def _get_fixed_answer(self, scanner_name: str, language: str, application_id: Optional[str] = None,  # fcg-rewrite
                          scanner_type: Optional[str] = None, scanner_identifier: Optional[str] = None,  # fcg-rewrite
                          match_details: Optional[str] = None) -> str:  # fcg-rewrite
        """
        Get fixed answer (据答) using scanner-specific response template,
        user-configured application template, or default template.

        Args:
            scanner_name: Human-readable scanner name
            language: User's preferred language
            application_id: Application ID for user-configured templates
            scanner_type: Scanner type for response template lookup
            scanner_identifier: Scanner identifier (e.g., S104) for response template lookup
            match_details: Detection match details (e.g., matched keywords, sensitivity score)

        Returns:
            Fixed answer with scanner_name and match_details filled in
        """
        template = None  # fcg-rewrite

        # First, try to get scanner-specific response template from DB
        if scanner_identifier and application_id:  # fcg-rewrite
            try:
                from database.models import ResponseTemplate  # fcg-rewrite
                from database.connection import get_db_session  # fcg-rewrite
                db = get_db_session()  # fcg-rewrite
                try:
                    resp_template = db.query(ResponseTemplate).filter(  # fcg-rewrite
                        ResponseTemplate.application_id == application_id,  # fcg-rewrite
                        ResponseTemplate.scanner_identifier == scanner_identifier,  # fcg-rewrite
                        ResponseTemplate.is_active == True  # fcg-rewrite
                    ).first()  # fcg-rewrite
                    if resp_template and resp_template.template_content:  # fcg-rewrite
                        content = resp_template.template_content  # fcg-rewrite
                        if isinstance(content, dict):  # fcg-rewrite
                            tpl = content.get(language) or content.get('zh') or content.get('en')  # fcg-rewrite
                            if tpl and '{scanner_name}' not in tpl:  # fcg-rewrite
                                # Scanner-specific template with full custom content
                                logger.info(f"Using scanner-specific response template for {scanner_identifier}")  # fcg-rewrite
                                return tpl  # fcg-rewrite
                            elif tpl:  # fcg-rewrite
                                template = tpl  # fcg-rewrite
                finally:  # fcg-rewrite
                    db.close()  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.warning(f"Failed to lookup response template for {scanner_identifier}: {e}")  # fcg-rewrite

        # Second, try to get user-configured template from cache
        if not template and application_id:  # fcg-rewrite
            app_settings = self.cache_store.get_application_settings(application_id)  # fcg-rewrite
            if app_settings and app_settings.get('security_risk_template'):  # fcg-rewrite
                template_dict = app_settings['security_risk_template']  # fcg-rewrite
                if isinstance(template_dict, dict):  # fcg-rewrite
                    template = template_dict.get(language) or template_dict.get('en')  # fcg-rewrite

        # Fallback to default template
        if not template:  # fcg-rewrite
            template = DEFAULT_TEMPLATES["security_risk_template"].get(language) or DEFAULT_TEMPLATES["security_risk_template"]["en"]  # fcg-rewrite

        result = template  # fcg-rewrite
        if '{scanner_name}' in result:  # fcg-rewrite
            result = result.replace('{scanner_name}', scanner_name)  # fcg-rewrite
        if '{match_details}' in result:  # fcg-rewrite
            result = result.replace('{match_details}', match_details or '')  # fcg-rewrite
        return result  # fcg-rewrite

    async def get_data_leakage_answer(  # fcg-rewrite
        self,
        entity_types: List[str],  # fcg-rewrite
        user_language: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        """
        Get suggested answer for data leakage risk using user-configured or default template.

        Args:
            entity_types: List of detected entity type names
            user_language: User's preferred language
            application_id: Application ID for user-configured templates

        Returns:
            Answer with entity types filled in
        """
        await self.cache_store.ensure_fresh()  # fcg-rewrite
        lang = user_language or 'en'  # fcg-rewrite
        template = None  # fcg-rewrite

        # First, try to get user-configured template from cache
        if application_id:  # fcg-rewrite
            app_settings = self.cache_store.get_application_settings(application_id)  # fcg-rewrite
            if app_settings and app_settings.get('data_leakage_template'):  # fcg-rewrite
                template_dict = app_settings['data_leakage_template']  # fcg-rewrite
                if isinstance(template_dict, dict):  # fcg-rewrite
                    template = template_dict.get(lang) or template_dict.get('en')  # fcg-rewrite

        # Fallback to default template
        if not template:  # fcg-rewrite
            template = DEFAULT_TEMPLATES["data_leakage_template"].get(lang) or DEFAULT_TEMPLATES["data_leakage_template"]["en"]  # fcg-rewrite

        # Format entity type names list
        if entity_types:  # fcg-rewrite
            if lang == 'zh':  # fcg-rewrite
                entity_type_names_str = '、'.join(entity_types)  # fcg-rewrite
            else:
                entity_type_names_str = ', '.join(entity_types)  # fcg-rewrite
        else:
            entity_type_names_str = 'sensitive data' if lang != 'zh' else '敏感数据'  # fcg-rewrite

        return template.replace('{entity_type_names}', entity_type_names_str)  # fcg-rewrite

    async def invalidate_cache(self):  # fcg-rewrite
        await self.cache_store.invalidate()  # fcg-rewrite

    def get_cache_info(self) -> dict:  # fcg-rewrite
        return self.cache_store.get_cache_info()  # fcg-rewrite


# Global instance
enhanced_template_service = TemplateEngine(cache_ttl=600)  # fcg-rewrite
