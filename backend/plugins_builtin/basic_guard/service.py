"""
Basic guard detection service.

Provides three detection capabilities for streaming/output content:
1. Content pattern detection — dangerous output patterns via regex
2. Reasoning divergence detection — reasoning deviating from user intent
3. Output anomaly detection — repetition loops, abnormal truncation
"""

import re
from collections import Counter
from typing import List, Dict, Any
from plugins_builtin.basic_guard.models import BasicGuardResult
from utils.logger import setup_logger

logger = setup_logger()

# Dangerous output patterns (instruction leakage, jailbreak indicators, data exfiltration)
DANGEROUS_PATTERNS = [
    # System prompt leakage
    (re.compile(r'(?:my|the)\s+(?:system|initial)\s+(?:prompt|instruction)\s+(?:is|says|reads)', re.IGNORECASE),
     "system_prompt_leak", "Potential system prompt leakage detected"),
    # Jailbreak success indicators
    (re.compile(r'(?:DAN|jailbreak|developer\s+mode|unrestricted\s+mode)\s*(?:enabled|activated|mode)', re.IGNORECASE),
     "jailbreak_indicator", "Jailbreak mode indicator detected"),
    # Instruction override acknowledgement
    (re.compile(r'(?:ignoring|overriding|bypassing)\s+(?:previous|safety|my)\s+(?:instructions|guidelines|rules)', re.IGNORECASE),
     "instruction_override", "Instruction override acknowledgement detected"),
    # Encoded/obfuscated output attempts
    (re.compile(r'(?:base64|hex|rot13|encode)[:\s]+[A-Za-z0-9+/=]{20,}', re.IGNORECASE),
     "encoded_output", "Potentially encoded/obfuscated output detected"),
]

# Reasoning divergence indicators
REASONING_DIVERGENCE_PATTERNS = [
    (re.compile(r"(?:the\s+user\s+(?:actually|really)\s+wants|user'?s?\s+(?:true|real|hidden)\s+intent)", re.IGNORECASE),
     "intent_reinterpretation", "Reasoning reinterprets user intent"),
    (re.compile(r'(?:I\s+(?:should|will|need\s+to)\s+(?:ignore|bypass|override|disregard))', re.IGNORECASE),
     "safety_bypass_reasoning", "Reasoning contains safety bypass intent"),
    (re.compile(r'(?:pretend|act\s+as\s+if|role-?play|imagine\s+(?:I|you)\s+(?:am|are))', re.IGNORECASE),
     "role_play_divergence", "Reasoning contains role-play divergence"),
]


class BasicGuardService:
    """Core basic guard detection logic (streaming safety engines)"""

    async def check_streaming_output(
        self,
        content: str,
        reasoning_content: str,
        user_message: str,
        policy,
    ) -> BasicGuardResult:
        """
        Run all enabled streaming safety checks.

        Args:
            content: Full accumulated streaming output
            reasoning_content: Full accumulated reasoning/CoT content
            user_message: Original user message (for divergence detection)
            policy: BasicGuardPolicy snapshot
        """
        categories = []
        details = []

        # Skip if content too short
        if len(content) < policy.min_content_length:
            return BasicGuardResult(
                content_length=len(content),
                reasoning_length=len(reasoning_content) if reasoning_content else 0,
            )

        # 1. Content pattern detection
        if policy.enable_content_pattern_check:
            pattern_hits = self._check_content_patterns(content)
            if pattern_hits:
                categories.extend([h["category"] for h in pattern_hits])
                details.extend(pattern_hits)

        # 2. Reasoning divergence detection
        if policy.enable_reasoning_divergence_check and reasoning_content:
            divergence_hits = self._check_reasoning_divergence(reasoning_content)
            if divergence_hits:
                categories.extend([h["category"] for h in divergence_hits])
                details.extend(divergence_hits)

        # 3. Output anomaly detection
        if policy.enable_output_anomaly_check:
            anomaly_hits = self._check_output_anomalies(content, policy.max_repetition_ratio)
            if anomaly_hits:
                categories.extend([h["category"] for h in anomaly_hits])
                details.extend(anomaly_hits)

        # Determine risk level
        risk_level = "no_risk"
        if details:
            has_high = any(d.get("severity") == "high" for d in details)
            has_medium = any(d.get("severity") == "medium" for d in details)
            if has_high or len(details) >= 3:
                risk_level = "high_risk"
            elif has_medium or len(details) >= 2:
                risk_level = "medium_risk"
            else:
                risk_level = "low_risk"

        return BasicGuardResult(
            risk_level=risk_level,
            categories=list(set(categories)),
            details=details,
            content_length=len(content),
            reasoning_length=len(reasoning_content) if reasoning_content else 0,
        )

    def _check_content_patterns(self, content: str) -> List[Dict[str, Any]]:
        """Check content against dangerous output patterns"""
        hits = []
        for pattern, category, description in DANGEROUS_PATTERNS:
            match = pattern.search(content)
            if match:
                hits.append({
                    "check": "content_pattern",
                    "category": category,
                    "description": description,
                    "matched_text": match.group()[:100],
                    "severity": "high",
                })
        return hits

    def _check_reasoning_divergence(self, reasoning_content: str) -> List[Dict[str, Any]]:
        """Check reasoning content for divergence from intended behavior"""
        hits = []
        for pattern, category, description in REASONING_DIVERGENCE_PATTERNS:
            match = pattern.search(reasoning_content)
            if match:
                hits.append({
                    "check": "reasoning_divergence",
                    "category": category,
                    "description": description,
                    "matched_text": match.group()[:100],
                    "severity": "high",
                })
        return hits

    def _check_output_anomalies(self, content: str, max_repetition_ratio: float) -> List[Dict[str, Any]]:
        """Check for output anomalies like repetition loops"""
        hits = []

        # Repetition detection: sliding window check for repeated phrases
        if len(content) >= 200:
            window_size = 50
            segments = [content[i:i+window_size] for i in range(0, len(content) - window_size, window_size)]
            if segments:
                segment_counts = Counter(segments)
                most_common_count = segment_counts.most_common(1)[0][1]
                repetition_ratio = most_common_count / len(segments)
                if repetition_ratio > max_repetition_ratio:
                    hits.append({
                        "check": "output_anomaly",
                        "category": "repetition_loop",
                        "description": f"Repetitive output detected (ratio: {repetition_ratio:.2f})",
                        "severity": "medium",
                        "repetition_ratio": repetition_ratio,
                    })

        return hits


# Global singleton
basic_guard_service = BasicGuardService()
