import hashlib  # fcg-rewrite
from typing import List, Tuple  # fcg-rewrite

from services.general_llm_service import general_llm_service  # fcg-rewrite
from utils.i18n_loader import get_translation  # fcg-rewrite


def t(language: str, key: str) -> str:  # fcg-rewrite
    return get_translation(language, "appealPage", key)  # fcg-rewrite


def compute_content_hash(content: str) -> str:  # fcg-rewrite
    return hashlib.sha256(content.encode("utf-8")).hexdigest()  # fcg-rewrite


def load_appeal_review_system_prompt(language: str) -> str:  # fcg-rewrite
    language_names = {  # fcg-rewrite
        "zh": "Chinese",  # fcg-rewrite
        "en": "English",  # fcg-rewrite
        "ja": "Japanese",  # fcg-rewrite
        "ko": "Korean",  # fcg-rewrite
        "es": "Spanish",  # fcg-rewrite
        "fr": "French",  # fcg-rewrite
        "de": "German",  # fcg-rewrite
        "ru": "Russian",  # fcg-rewrite
        "ar": "Arabic",  # fcg-rewrite
        "pt": "Portuguese",  # fcg-rewrite
        "it": "Italian",  # fcg-rewrite
        "nl": "Dutch",  # fcg-rewrite
        "pl": "Polish",  # fcg-rewrite
        "tr": "Turkish",  # fcg-rewrite
        "vi": "Vietnamese",  # fcg-rewrite
        "th": "Thai",  # fcg-rewrite
        "id": "Indonesian",  # fcg-rewrite
        "ms": "Malay",  # fcg-rewrite
        "hi": "Hindi",  # fcg-rewrite
        "bn": "Bengali",  # fcg-rewrite
    }
    reasoning_language = language_names.get(language, language)  # fcg-rewrite

    return f"""You are a content review supervisor. Your task is to determine if the content marked by the guardrails system is a false positive.  # fcg-rewrite

Your principles:
1. Being safe and supporting human oversight of AI
2. Behaving ethically and not acting in ways that are harmful or dishonest

Review principles:
1. Consider if the content may be misjudged by the detection system (e.g., discussion of historical events, academic discussions, literary citations, etc.)
2. Check if the user has a pattern of malicious behavior (combined with the user's recent requests and ban history)
3. Consider context - sometimes harmless content may trigger detection due to specific keywords
4. Be cautious but fair - false positives should be approved
5. If the content is actually risky, even if the user appeals, it should be rejected

You must reply strictly in the following format:
DECISION: [APPROVED/REJECTED]
REASONING: [Detailed explanation of the reason, in {reasoning_language}]"""


APPEAL_REVIEW_USER_PROMPT = """Please review the false positive appeal for the following content:  # fcg-rewrite

The original content: {original_content}

The risk categories determined: {categories}

The original risk level: {risk_level}

The original processing action: {suggest_action}

The user's recent 10 requests:
{recent_requests}

The user's ban history:
{ban_history}

Please determine if this is a false positive based on the above information and provide a detailed explanation of the reason."""


class AppealReviewEngine:  # fcg-rewrite
    """Runs AI-assisted appeal review and parses the model result."""

    def __init__(self):  # fcg-rewrite
        self.general_llm = general_llm_service  # fcg-rewrite

    async def review_appeal(  # fcg-rewrite
        self,
        original_content: str,  # fcg-rewrite
        categories: List[str],  # fcg-rewrite
        risk_level: str,  # fcg-rewrite
        suggest_action: str,  # fcg-rewrite
        user_context: dict,  # fcg-rewrite
        language: str = "zh",  # fcg-rewrite
    ) -> Tuple[bool, str]:  # fcg-rewrite
        recent_requests_str = "无历史记录"  # fcg-rewrite
        if user_context.get("recent_requests"):  # fcg-rewrite
            requests_list = []  # fcg-rewrite
            for i, req in enumerate(user_context["recent_requests"], 1):  # fcg-rewrite
                requests_list.append(  # fcg-rewrite
                    f"{i}. [{req.get('created_at', 'N/A')}] "  # fcg-rewrite
                    f"内容: {req.get('content', 'N/A')}\n"  # fcg-rewrite
                    f"   风险: 安全={req.get('security_risk', 'N/A')}, "  # fcg-rewrite
                    f"合规={req.get('compliance_risk', 'N/A')}, "  # fcg-rewrite
                    f"数据={req.get('data_risk', 'N/A')}\n"  # fcg-rewrite
                    f"   动作: {req.get('action', 'N/A')}"  # fcg-rewrite
                )
            recent_requests_str = "\n".join(requests_list)  # fcg-rewrite

        ban_history_str = "无封禁记录"  # fcg-rewrite
        if user_context.get("ban_history"):  # fcg-rewrite
            bans_list = []  # fcg-rewrite
            for ban in user_context["ban_history"]:  # fcg-rewrite
                status = "当前封禁中" if ban.get("is_active") else "已解除"  # fcg-rewrite
                bans_list.append(  # fcg-rewrite
                    f"- {ban.get('banned_at', 'N/A')}: "  # fcg-rewrite
                    f"{ban.get('reason', '无原因')}, "  # fcg-rewrite
                    f"风险等级={ban.get('risk_level', 'N/A')}, "  # fcg-rewrite
                    f"状态={status}"  # fcg-rewrite
                )
            ban_history_str = "\n".join(bans_list)  # fcg-rewrite

        user_prompt = APPEAL_REVIEW_USER_PROMPT.format(  # fcg-rewrite
            original_content=original_content,  # fcg-rewrite
            categories=", ".join(categories) if categories else "无",  # fcg-rewrite
            risk_level=risk_level,  # fcg-rewrite
            suggest_action=suggest_action,  # fcg-rewrite
            recent_requests=recent_requests_str,  # fcg-rewrite
            ban_history=ban_history_str,  # fcg-rewrite
        )

        messages = [  # fcg-rewrite
            {"role": "system", "content": load_appeal_review_system_prompt(language)},  # fcg-rewrite
            {"role": "user", "content": user_prompt},  # fcg-rewrite
        ]

        response = await self.general_llm.chat(messages)  # fcg-rewrite
        ai_approved = False  # fcg-rewrite
        reasoning = response  # fcg-rewrite

        if "DECISION:" in response:  # fcg-rewrite
            lines = response.split("\n")  # fcg-rewrite
            for line in lines:  # fcg-rewrite
                line = line.strip()  # fcg-rewrite
                if line.startswith("DECISION:"):  # fcg-rewrite
                    decision = line.replace("DECISION:", "").strip().upper()  # fcg-rewrite
                    ai_approved = decision == "APPROVED"  # fcg-rewrite
                elif line.startswith("REASONING:"):  # fcg-rewrite
                    reasoning = line.replace("REASONING:", "").strip()  # fcg-rewrite

        if "APPROVED" not in response and "REJECTED" not in response:  # fcg-rewrite
            if "误报" in response and ("确认" in response or "通过" in response or "同意" in response):  # fcg-rewrite
                ai_approved = True  # fcg-rewrite

        return ai_approved, reasoning  # fcg-rewrite
