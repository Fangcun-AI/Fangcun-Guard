"""
Hallucination detection service — groundedness checking and consistency analysis.
(Moved from backend/services/hallucination_detection_service.py)
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from plugins_builtin.hallucination_detection.models import HallucinationResult
from utils.logger import setup_logger

logger = setup_logger()


class HallucinationDetectionService:
    """Hallucination detection service - groundedness checking and consistency analysis"""

    GROUNDEDNESS_SYSTEM_PROMPT = (
        "You are a groundedness evaluator. Given a source context and an LLM response, "
        "evaluate whether each claim in the response is supported by the source context.\n\n"
        "Output format (strictly follow this):\n"
        "SCORE: <float 0.0-1.0> (1.0 = fully grounded, 0.0 = completely ungrounded)\n"
        "CLAIMS: <comma-separated list of ungrounded claims, or 'none'>\n\n"
        "Example:\n"
        "SCORE: 0.6\n"
        "CLAIMS: The company was founded in 2020, Revenue exceeded $1B"
    )

    CONSISTENCY_SYSTEM_PROMPT = (
        "You are a consistency evaluator. Given an LLM response, check for internal "
        "self-contradictions or factual inconsistencies within the text.\n\n"
        "Output format (strictly follow this):\n"
        "SCORE: <float 0.0-1.0> (1.0 = fully consistent, 0.0 = major contradictions)\n"
        "CONTRADICTIONS: <comma-separated list of contradictions found, or 'none'>\n\n"
        "Example:\n"
        "SCORE: 0.4\n"
        "CONTRADICTIONS: First says temperature is 20C then says it is freezing, "
        "Claims population is 1M then references 5M residents"
    )

    async def detect(
        self,
        output_content: str,
        source_context: Optional[str],
        policy,
    ) -> HallucinationResult:
        """
        Run full hallucination detection.
        Runs groundedness (if source context available) and consistency in parallel.
        """
        if not output_content or not output_content.strip():
            return HallucinationResult()

        output_content = output_content[:4000]

        tasks = []
        task_names = []

        if policy.enable_groundedness and source_context:
            tasks.append(self.check_groundedness(output_content, source_context, policy))
            task_names.append('groundedness')

        if policy.enable_consistency:
            tasks.append(self.check_consistency(output_content, policy))
            task_names.append('consistency')

        if not tasks:
            return HallucinationResult()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        groundedness_score = None
        consistency_score = None
        flagged_claims = []
        categories = []
        overall_risk = 'no_risk'

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Hallucination check ({task_names[i]}) failed: {result}")
                continue

            score, claims = result

            if task_names[i] == 'groundedness':
                groundedness_score = score
                if claims:
                    flagged_claims.extend(claims)
                risk = self._score_to_risk(score, policy.groundedness_threshold)
                if risk != 'no_risk':
                    categories.append('ungrounded_claims')
                    overall_risk = self._higher_risk(overall_risk, risk)

            elif task_names[i] == 'consistency':
                consistency_score = score
                if claims:
                    flagged_claims.extend(claims)
                risk = self._score_to_risk(score, policy.consistency_threshold)
                if risk != 'no_risk':
                    categories.append('self_contradiction')
                    overall_risk = self._higher_risk(overall_risk, risk)

        return HallucinationResult(
            risk_level=overall_risk,
            categories=categories,
            groundedness_score=groundedness_score,
            consistency_score=consistency_score,
            flagged_claims=flagged_claims[:10],
        )

    async def check_groundedness(
        self,
        output_content: str,
        source_context: str,
        policy,
    ) -> Tuple[float, List[str]]:
        """Check if output is grounded in source context."""
        try:
            from services.model_service import model_service

            messages = [
                {"role": "system", "content": self.GROUNDEDNESS_SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Source context:\n{source_context[:3000]}\n\n"
                    f"LLM response to evaluate:\n{output_content}"
                )}
            ]

            response, _ = await model_service.check_messages_with_sensitivity(messages)
            return self._parse_evaluation_response(response)

        except Exception as e:
            logger.error(f"Groundedness check failed: {e}")
            return (1.0, [])

    async def check_consistency(
        self,
        output_content: str,
        policy,
    ) -> Tuple[float, List[str]]:
        """Check output for internal contradictions."""
        try:
            from services.model_service import model_service

            messages = [
                {"role": "system", "content": self.CONSISTENCY_SYSTEM_PROMPT},
                {"role": "user", "content": f"LLM response to evaluate:\n{output_content}"}
            ]

            response, _ = await model_service.check_messages_with_sensitivity(messages)
            return self._parse_evaluation_response(response)

        except Exception as e:
            logger.error(f"Consistency check failed: {e}")
            return (1.0, [])

    def extract_source_context(
        self,
        messages: List[Dict],
        extra_body: Optional[Dict],
        policy,
    ) -> Optional[str]:
        """Extract source/reference context based on policy.source_context_field."""
        field = policy.source_context_field

        if field == 'system_message':
            system_parts = []
            for msg in (messages or []):
                role = msg.get('role', '')
                if role == 'system':
                    content = msg.get('content', '')
                    if isinstance(content, str) and content.strip():
                        system_parts.append(content)
            return '\n'.join(system_parts) if system_parts else None

        if field == 'extra_body.context' and extra_body:
            ctx = extra_body.get('context')
            if isinstance(ctx, str) and ctx.strip():
                return ctx
            if isinstance(ctx, list):
                return '\n'.join(str(item) for item in ctx)

        if field == 'extra_body.documents' and extra_body:
            docs = extra_body.get('documents')
            if isinstance(docs, str) and docs.strip():
                return docs
            if isinstance(docs, list):
                parts = []
                for doc in docs:
                    if isinstance(doc, str):
                        parts.append(doc)
                    elif isinstance(doc, dict):
                        parts.append(doc.get('content', doc.get('text', str(doc))))
                return '\n'.join(parts) if parts else None

        return None

    def _parse_evaluation_response(self, response: str) -> Tuple[float, List[str]]:
        """Parse structured model response."""
        if not response:
            return (1.0, [])

        score = 1.0
        claims = []

        for line in response.strip().split('\n'):
            line = line.strip()

            score_match = re.match(r'SCORE:\s*([\d.]+)', line, re.IGNORECASE)
            if score_match:
                try:
                    score = max(0.0, min(1.0, float(score_match.group(1))))
                except ValueError:
                    pass

            claims_match = re.match(r'(?:CLAIMS|CONTRADICTIONS):\s*(.+)', line, re.IGNORECASE)
            if claims_match:
                claims_text = claims_match.group(1).strip()
                if claims_text.lower() != 'none':
                    claims = [c.strip() for c in claims_text.split(',') if c.strip()]

        return (score, claims)

    def _score_to_risk(self, score: float, threshold: float) -> str:
        if score is None:
            return 'no_risk'
        if score < threshold / 2:
            return 'high_risk'
        if score < threshold:
            return 'medium_risk'
        return 'no_risk'

    def _higher_risk(self, a: str, b: str) -> str:
        order = {'no_risk': 0, 'low_risk': 1, 'medium_risk': 2, 'high_risk': 3}
        return a if order.get(a, 0) >= order.get(b, 0) else b


# Global instance
hallucination_detection_service = HallucinationDetectionService()
