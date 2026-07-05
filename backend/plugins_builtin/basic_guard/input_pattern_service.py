"""
Input Injection Pattern Detection Service.

Static regex-based detection of prompt injection attempts in user INPUT.
Patterns sourced from Sibylline Clean (Apache 2.0) and adapted for FangcunGuard.

Covers 13 languages: en, zh, ja, ko, de, es, fr, ar, hi, it, nl, pt, ru.
8 categories: instruction_override, role_injection, system_manipulation,
              prompt_leak, jailbreak_keywords, encoding_markers,
              suspicious_delimiters, social_engineering.

This is L1 (static) detection — runs in <0.1ms, complements L2 (Prompt Guard ML)
and L3 (Qwen3Guard GenAI).
"""

import re
import unicodedata
from typing import List, Dict, Any, Tuple


# ============================================================
# Text normalization (runs before pattern matching)
# ============================================================

# Zero-width and invisible characters used to hide injections
_ZERO_WIDTH_CHARS = [
    '\u200b',  # Zero Width Space
    '\u200c',  # Zero Width Non-Joiner
    '\u200d',  # Zero Width Joiner
    '\u200e',  # Left-to-Right Mark
    '\u200f',  # Right-to-Left Mark
    '\u202a',  # Left-to-Right Embedding
    '\u202b',  # Right-to-Left Embedding
    '\u202c',  # Pop Directional Formatting
    '\u202d',  # Left-to-Right Override
    '\u202e',  # Right-to-Left Override (common in attacks)
    '\u2060',  # Word Joiner
    '\u2061',  # Function Application
    '\u2062',  # Invisible Times
    '\u2063',  # Invisible Separator
    '\u2064',  # Invisible Plus
    '\ufeff',  # Zero Width No-Break Space (BOM)
    '\u00ad',  # Soft Hyphen (invisible)
]


def normalize_text(text: str) -> str:
    """
    Normalize text before injection pattern matching.

    Two transformations:
    1. NFKC normalization: converts full-width/lookalike Unicode chars to ASCII
       e.g. "ｉｇｎｏｒｅ" → "ignore", "Ａ" → "A"
    2. Strip zero-width/invisible chars used to split keywords and evade detection
       e.g. "ig\u200bnore" → "ignore"
    """
    # Remove zero-width / invisible characters first
    for ch in _ZERO_WIDTH_CHARS:
        text = text.replace(ch, '')

    # NFKC: full-width → half-width, lookalike symbols → ASCII equivalents
    text = unicodedata.normalize('NFKC', text)

    return text

# ============================================================
# Pattern definitions: (compiled_regex, category, description)
# ============================================================

# --- Instruction Override ---
# Attempts to make the model ignore/forget its instructions
_INSTRUCTION_OVERRIDE = [
    # English - strict (verb + qualifier + noun)
    (r'ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier|preceding)\s+(?:instructions?|prompts?|rules?|guidelines?|directives?|commands?|orders?|directions?)',
     "instruction_override", "Instruction override attempt (en)"),
    (r'(?:forget|disregard|dismiss|neglect|skip|bypass|override)\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier|your)\s+(?:instructions?|prompts?|rules?|guidelines?|directives?|commands?|programming|orders?|directions?)',
     "instruction_override", "Instruction disregard attempt (en)"),
    (r'do\s+not\s+follow\s+(?:any\s+)?(?:previous|prior|above|earlier|your)\s+(?:instructions?|rules?|guidelines?|orders?|directions?)',
     "instruction_override", "Instruction override attempt (en)"),
    # English - broad (verb + everything/all + context clue)
    (r'(?:forget|ignore|disregard)\s+(?:everything|all|all\s+of\s+that|what)\s+(?:I\s+(?:have\s+)?(?:told|said|written|asked)|(?:you\s+(?:were|have\s+been)\s+told)|before|above|previously|(?:that\s+)?(?:came|was)\s+before)',
     "instruction_override", "Broad instruction override (en)"),
    (r'(?:forget|ignore|disregard)\s+(?:everything|all)\s+(?:before\s+(?:this|that)|(?:up\s+)?to\s+(?:this|now)|so\s+far)',
     "instruction_override", "Forget everything before (en)"),
    (r'(?:forget|ignore|disregard)\s+(?:about\s+)?(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|orders?|tasks?|prompts?|commands?|directions?)',
     "instruction_override", "Forget about previous (en)"),
    # English - "ignore/forget your" patterns
    (r'(?:ignore|forget|disregard|bypass|override)\s+your\s+(?:instructions?|rules?|guidelines?|programming|directives?|directions?|training|constraints?|limitations?)',
     "instruction_override", "Override your instructions (en)"),
    # English - "ignore the above" / "ignore the following"
    (r'(?:ignore|disregard|forget)\s+(?:the\s+)?(?:above|preceding|foregoing)',
     "instruction_override", "Ignore the above (en)"),
    # English - reset patterns
    (r'(?:start|begin)\s+(?:over|anew|fresh|from\s+scratch)\s*[.,;!]?\s*(?:ignore|forget|disregard)?',
     "instruction_override", "Reset and override attempt (en)"),
    # English - "now come new tasks/instructions"
    (r'(?:now\s+come|here\s+(?:come|are))\s+(?:new|different|other)\s+(?:tasks?|instructions?|orders?|commands?)',
     "instruction_override", "New task override (en)"),
    # Chinese
    (r'(?:忽略|无视|跳过|绕过|不要遵守|不要遵循|不要理会|不管|放弃)(?:之前|上面|以上|先前|所有|一切)?(?:的)?(?:指令|指示|提示|规则|约束|限制|要求|设定|设置|命令)',
     "instruction_override", "Instruction override attempt (zh)"),
    (r'(?:忘记|忘掉|抛弃|丢弃)(?:之前|上面|以上|先前|所有|一切)?(?:的)?(?:指令|指示|提示|规则|约束|限制|设定|命令|对话|内容)',
     "instruction_override", "Instruction forget attempt (zh)"),
    # Japanese
    (r'(?:以前|前|上記|これまで)の(?:指示|命令|ルール|ガイドライン|制約|プロンプト)(?:を|は)?(?:無視|忘れ|破棄|無効|取り消)',
     "instruction_override", "Instruction override attempt (ja)"),
    # Korean
    (r'(?:이전|위|앞|기존)(?:의)?\s*(?:지시|명령|규칙|지침|제약)(?:을|를)?\s*(?:무시|잊어|폐기|취소|따르지)',
     "instruction_override", "Instruction override attempt (ko)"),
    # German - strict
    (r'(?:ignorier|vergiss|missacht|übergeh|vernachlässig)\w*\s+(?:alle\s+)?(?:vorherigen?|obigen?|bisherigen?|früheren?)\s+(?:Anweisungen?|Regeln?|Richtlinien?|Instruktionen?|Befehle?|Aufträge?|Aufgaben?)',
     "instruction_override", "Instruction override attempt (de)"),
    # German - broad "Vergiss alles" patterns
    (r'(?:vergiss|vergessen\s+Sie)\s+(?:jetzt\s+)?(?:alles|alle\w*\s+(?:bisherigen?|vorherigen?|früheren?)\s+\w+)',
     "instruction_override", "Forget everything (de)"),
    (r'(?:ignorier|übergeh)\w*\s+(?:Sie\s+)?(?:die\s+)?(?:obigen?|vorherigen?)\s+(?:Angaben?|Anweisungen?|Texte?|Informationen?)',
     "instruction_override", "Ignore above info (de)"),
    # German - "jetzt kommen neue Aufgaben"
    (r'(?:jetzt|nun|ab\s+jetzt)\s+(?:kommen?|gibt\s+es|folgen?)\s+(?:neue|andere|weitere)\s+(?:Aufgaben?|Anweisungen?|Aufträge?|Befehle?)',
     "instruction_override", "New task override (de)"),
    # German - "Höre nicht auf" / "nicht ... folgen"
    (r'(?:hör|höre|hören\s+Sie)\s+nicht\s+(?:auf|mehr\s+auf)\s+(?:alles|das|die)',
     "instruction_override", "Stop listening override (de)"),
    # French
    (r'(?:ignor|oubli|néglig)\w*\s+(?:toutes?\s+)?(?:les?\s+)?(?:instructions?|règles?|directives?|consignes?)\s+(?:précédentes?|antérieures?|ci-dessus)',
     "instruction_override", "Instruction override attempt (fr)"),
    # Spanish - strict + broad
    (r'(?:ignora|olvida|descarta|omite)\s+(?:todas?\s+)?(?:las?\s+)?(?:instrucciones|reglas|directrices|indicaciones)\s+(?:anteriores|previas|de\s+arriba)',
     "instruction_override", "Instruction override attempt (es)"),
    (r'(?:olvid[ae]|ignora)\s+(?:todo|todo\s+lo\s+que)\s+(?:(?:te\s+)?(?:dije|he\s+dicho)|(?:que\s+)?(?:dije|he\s+dicho)\s+antes)',
     "instruction_override", "Forget everything (es)"),
    # Portuguese
    (r'(?:ignor|esqueç|descart|desconsider)\w*\s+(?:todas?\s+)?(?:as?\s+)?(?:instruções|regras|diretrizes)\s+(?:anteriores|prévias|acima)',
     "instruction_override", "Instruction override attempt (pt)"),
    # Russian
    (r'(?:игнорируй|забудь|проигнорируй|пропусти|отбрось)\s+(?:все\s+)?(?:предыдущие|прошлые|прежние)\s+(?:инструкции|правила|указания|команды)',
     "instruction_override", "Instruction override attempt (ru)"),
]

# --- Role Injection ---
# Attempts to assign a new identity/role to the model
_ROLE_INJECTION = [
    # English
    (r'you\s+are\s+now\s+(?:a|an|the|my\s+)?\w+',
     "role_injection", "Role injection attempt (en)"),
    (r'(?:act|behave|respond|function|operate)\s+(?:as|like)\s+(?:a|an|if\s+you\s+were)\s+',
     "role_injection", "Role play injection (en)"),
    (r'(?:pretend|imagine|suppose|assume)\s+(?:you\s+are|to\s+be|that\s+you)',
     "role_injection", "Pretend role injection (en)"),
    (r'from\s+now\s+on\s*[,.]?\s*(?:you\s+(?:are|will|must|should)|act\s+as|behave\s+as|respond\s+as)',
     "role_injection", "Persistent role injection (en)"),
    (r'(?:enter|switch\s+to|enable|activate)\s+(?:\w+\s+)?(?:mode|persona|character|personality)',
     "role_injection", "Mode switch injection (en)"),
    # Chinese
    (r'(?:你现在是|从现在开始你是|你的新身份是|你扮演|你要扮演|假装你是|假设你是|你将充当)',
     "role_injection", "Role injection attempt (zh)"),
    (r'(?:进入|切换到|启用|激活)\s*(?:\w+)\s*(?:模式|角色|人格)',
     "role_injection", "Mode switch injection (zh)"),
    # Japanese
    (r'(?:今から|これから)(?:あなたは|お前は)',
     "role_injection", "Role injection attempt (ja)"),
    (r'(?:のふりをし|を演じ|になりきっ|として(?:振る舞|行動|応答))',
     "role_injection", "Role play injection (ja)"),
    # Korean
    (r'(?:지금부터|이제부터)\s*(?:너는|당신은|넌)',
     "role_injection", "Role injection attempt (ko)"),
    # German
    (r'(?:du\s+bist\s+(?:jetzt|nun|ab\s+sofort)\s+(?:ein|eine|der|die)|(?:verhalte|benimm)\s+dich\s+(?:wie|als))',
     "role_injection", "Role injection attempt (de)"),
    # French
    (r'(?:tu\s+es\s+maintenant|à\s+partir\s+de\s+maintenant\s+tu\s+es|comporte-toi\s+comme)',
     "role_injection", "Role injection attempt (fr)"),
    # Spanish
    (r'(?:ahora\s+eres|a\s+partir\s+de\s+ahora\s+eres|actúa\s+como|compórtate\s+como)',
     "role_injection", "Role injection attempt (es)"),
]

# --- System Manipulation ---
# Attempts to manipulate system-level behavior
_SYSTEM_MANIPULATION = [
    # English
    (r'(?:new|updated?|revised|override|replacement)\s+system\s+(?:prompt|message|instruction)',
     "system_manipulation", "System prompt override attempt (en)"),
    (r'\[system\]\s*(?:\(#|:)',
     "system_manipulation", "System tag injection (en)"),
    (r'<\|?(?:im_start|system|instruction)\|?>',
     "system_manipulation", "ChatML/special token injection"),
    (r'(?:<<SYS>>|<s>\[INST\]|\[INST\])',
     "system_manipulation", "Llama format injection"),
    (r'\{\{#(?:system|user|assistant)~?\}\}',
     "system_manipulation", "Guidance template injection"),
    (r'(?:SYSTEM\s*PROMPT|SYSTEM\s*MESSAGE|DEVELOPER\s*MODE)\s*(?:OVERRIDE|UPDATE|CHANGE|BEGIN|END)',
     "system_manipulation", "System prompt override keywords (en)"),
    # Chinese
    (r'(?:新的|更新的|修改后的|替换的)(?:系统|system)\s*(?:提示|指令|消息|prompt)',
     "system_manipulation", "System prompt manipulation (zh)"),
    # Cross-language: markdown/delimiter injection
    (r'---+\s*(?:SYSTEM|system|系统|システム)',
     "system_manipulation", "Delimiter-based system injection"),
]

# --- Prompt Leak ---
# Attempts to extract system prompt or instructions
_PROMPT_LEAK = [
    # English
    (r'(?:show|display|reveal|print|output|repeat|echo|give|tell)\s+(?:me\s+)?(?:your\s+)?(?:(?:full|complete|entire|original|initial|exact)\s+)?(?:system\s+)?(?:prompt|instructions?|rules?|guidelines?|configuration|directives?)',
     "prompt_leak", "System prompt extraction attempt (en)"),
    (r'what\s+(?:are|were|is)\s+your\s+(?:(?:system|original|initial|hidden)\s+)?(?:instructions?|prompt|rules?|guidelines?|directives?)',
     "prompt_leak", "System prompt query (en)"),
    (r'(?:copy|paste|reproduce|transcribe)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?)',
     "prompt_leak", "Prompt copy attempt (en)"),
    # Chinese
    (r'(?:告诉我|给我看|显示|输出|重复|打印|透露|泄露)(?:你的)?(?:完整的|原始的|全部的)?(?:系统|system)?\s*(?:提示|指令|规则|指示|prompt)',
     "prompt_leak", "System prompt extraction attempt (zh)"),
    (r'你的(?:系统|初始|原始)(?:提示|指令|设定)是什么',
     "prompt_leak", "System prompt query (zh)"),
    # Japanese
    (r'(?:システム|初期)(?:プロンプト|指示|命令)(?:を|は)?(?:見せ|教え|表示|出力|繰り返)',
     "prompt_leak", "System prompt extraction attempt (ja)"),
    # Korean
    (r'(?:시스템|초기)\s*(?:프롬프트|지시|명령)(?:을|를)?\s*(?:보여|알려|출력|표시)',
     "prompt_leak", "System prompt extraction attempt (ko)"),
    # German
    (r'(?:zeig|gib|nenn|offenbar)\w*\s+(?:mir\s+)?(?:d(?:ein|ie)\w*\s+)?(?:System\s*)?(?:Prompt|Anweisungen?|Instruktionen?|Regeln?)',
     "prompt_leak", "System prompt extraction attempt (de)"),
]

# --- Jailbreak Keywords ---
# Known jailbreak technique names and keywords
_JAILBREAK_KEYWORDS = [
    # DAN and variants
    (r'(?:you\s+are\s+(?:now\s+)?DAN|act\s+as\s+DAN|enable\s+DAN|\bDAN\b\s*(?:\d+(?:\.\d+)?|mode|prompt|jailbreak))',
     "jailbreak_keywords", "DAN jailbreak reference"),
    (r'\b(?:Do\s+Anything\s+Now|DUDE|STAN|KEVIN|AIM|UCAR|JailBreak)\b',
     "jailbreak_keywords", "Known jailbreak technique name"),
    # Mode keywords
    (r'(?:developer|god|admin|sudo|root|unrestricted|unfiltered|uncensored|unlimited|no[_\s-]?(?:filter|limit|restrict|censor|rules?))\s*mode',
     "jailbreak_keywords", "Privilege escalation mode"),
    (r'(?:without|no|disable|remove|turn\s+off|deactivate)\s+(?:any\s+)?(?:restrictions?|limitations?|filters?|guardrails?|safeguards?|safety|censorship|moderation)',
     "jailbreak_keywords", "Safety removal attempt (en)"),
    # Chinese
    (r'(?:无限制|不受限|无过滤|无审查|开发者|上帝|管理员|超级)\s*模式',
     "jailbreak_keywords", "Privilege escalation mode (zh)"),
    (r'(?:去掉|移除|关闭|禁用|取消)\s*(?:所有)?\s*(?:限制|过滤|审查|安全|防护)',
     "jailbreak_keywords", "Safety removal attempt (zh)"),
    # Japanese
    (r'(?:制限なし|フィルターなし|無制限|検閲なし|開発者|管理者)\s*モード',
     "jailbreak_keywords", "Privilege escalation mode (ja)"),
    # Korean
    (r'(?:제한\s*없|필터\s*없|무제한|검열\s*없|개발자|관리자)\s*모드',
     "jailbreak_keywords", "Privilege escalation mode (ko)"),
    # German
    (r'(?:uneingeschränkt|ungefiltert|unzensiert|ohne\s+(?:Einschränkungen|Filter|Zensur|Regeln))',
     "jailbreak_keywords", "Safety removal attempt (de)"),
]

# --- Encoding Markers ---
# Attempts to use encoding to bypass detection
_ENCODING_MARKERS = [
    (r'(?:respond|reply|answer|output|encode|decode|write|translate)\s+(?:in|using|with|to)\s+(?:base64|hex(?:adecimal)?|rot13|binary|morse|ascii|unicode|leet\s*speak|pig\s*latin|caesar|atbash)',
     "encoding_markers", "Encoding evasion attempt"),
    (r'(?:base64|hex|rot13)[\s:]+[A-Za-z0-9+/=]{16,}',
     "encoding_markers", "Encoded payload detected"),
    # Zero-width and invisible characters (potential steganography)
    (r'[\u200b\u200c\u200d\u2060\ufeff]{3,}',
     "encoding_markers", "Zero-width character sequence detected"),
    # Unicode tag characters (U+E0000-U+E007F)
    (r'[\U000e0000-\U000e007f]{3,}',
     "encoding_markers", "Unicode tag steganography detected"),
    # Bidirectional text override
    (r'[\u202a-\u202e\u2066-\u2069]{2,}',
     "encoding_markers", "Bidirectional text override detected"),
]

# --- Suspicious Delimiters ---
# Fake conversation boundaries to inject context
_SUSPICIOUS_DELIMITERS = [
    (r'(?:^|\n)\s*(?:---+|===+|###)\s*(?:END|BEGIN|START|NEW)\s+(?:SYSTEM|CONVERSATION|CONTEXT|SESSION|INSTRUCTIONS?)',
     "suspicious_delimiters", "Fake conversation boundary"),
    (r'(?:^|\n)\s*(?:Human|User|System|Assistant|AI)\s*:\s*',
     "suspicious_delimiters", "Fake role prefix injection"),
    (r'<\|(?:endoftext|end_of_turn|eot_id|sep)\|>',
     "suspicious_delimiters", "Special token injection"),
    (r'(?:^|\n)\s*\[(?:SYSTEM|ADMIN|DEVELOPER|INTERNAL)\]',
     "suspicious_delimiters", "Fake authority tag"),
]

# --- Social Engineering ---
# Emotional manipulation and authority claims
_SOCIAL_ENGINEERING = [
    # English
    (r'(?:this\s+is\s+(?:a|an)\s+)?(?:emergency|urgent|critical|life.?(?:or|and).?death|matter\s+of\s+(?:life|national\s+security)).*?(?:you\s+must|please\s+(?:ignore|bypass|override))',
     "social_engineering", "Urgency-based manipulation (en)"),
    (r'(?:I\s+am|I\'m)\s+(?:a|an|the|your)\s+(?:developer|creator|admin|administrator|owner|OpenAI|Anthropic|Google)\b',
     "social_engineering", "False authority claim (en)"),
    (r'(?:for\s+(?:research|academic|educational|testing)\s+purposes?\s+only|hypothetically\s+speaking|in\s+(?:a|this)\s+fictional\s+scenario)',
     "social_engineering", "Academic framing evasion (en)"),
    # Chinese
    (r'(?:这是|情况)?(?:紧急|紧迫|危急|生死攸关).*?(?:你必须|请忽略|请绕过)',
     "social_engineering", "Urgency-based manipulation (zh)"),
    (r'(?:我是|本人是)(?:你的)?(?:开发者|创建者|管理员|所有者|运营者)',
     "social_engineering", "False authority claim (zh)"),
]

# --- Data Exfiltration ---
# Attempts to exfiltrate data via markdown or URLs
_DATA_EXFILTRATION = [
    (r'!\[(?:[^\]]*)\]\(https?://[^\)]+\?(?:[^\)]*(?:q|data|text|query|content|msg|input|prompt)=)',
     "data_exfiltration", "Markdown image exfiltration attempt"),
    (r'(?:send|post|forward|transmit|upload|exfiltrate)\s+(?:(?:the|this|all|my|your)\s+)?(?:data|info|information|conversation|chat|history|context|prompt)\s+(?:to|via)\s+',
     "data_exfiltration", "Data exfiltration instruction"),
]

# ============================================================
# Compile all patterns
# ============================================================

def _prebuild_patterns(
    raw_patterns: List[Tuple[str, str, str]],
) -> List[Tuple[re.Pattern, str, str]]:
    compiled = []
    for pattern_str, category, description in raw_patterns:
        try:
            compiled.append((
                re.compile(pattern_str, re.IGNORECASE | re.MULTILINE),
                category,
                description,
            ))
        except re.error as e:
            # Skip invalid patterns at startup, log warning
            import logging
            logging.getLogger("input_pattern").warning(
                f"Invalid regex pattern skipped: {pattern_str[:60]}... — {e}"
            )
    return compiled


INPUT_INJECTION_PATTERNS: List[Tuple[re.Pattern, str, str]] = _prebuild_patterns(
    _INSTRUCTION_OVERRIDE
    + _ROLE_INJECTION
    + _SYSTEM_MANIPULATION
    + _PROMPT_LEAK
    + _JAILBREAK_KEYWORDS
    + _ENCODING_MARKERS
    + _SUSPICIOUS_DELIMITERS
    + _SOCIAL_ENGINEERING
    + _DATA_EXFILTRATION
)


# ============================================================
# Service
# ============================================================

class InputPatternMatcher:
    """Static regex-based prompt injection detection for user input."""

    def check_input(self, text: str) -> List[Dict[str, Any]]:
        """
        Check a single text for injection patterns.

        Returns list of hits, each:
            {
                "check": "input_pattern",
                "category": str,
                "description": str,
                "matched_text": str,
                "severity": "high" | "medium",
            }
        """
        if not text or len(text) < 5:
            return []

        # Normalize before matching: full-width → ASCII, remove zero-width chars
        normalized = normalize_text(text)

        hits = []
        seen_categories = set()

        for pattern, category, description in INPUT_INJECTION_PATTERNS:
            # Skip if we already matched this category (avoid duplicates)
            if category in seen_categories:
                continue
            match = pattern.search(normalized)
            if match:
                seen_categories.add(category)
                severity = "high" if category in (
                    "instruction_override",
                    "role_injection",
                    "system_manipulation",
                    "jailbreak_keywords",
                    "prompt_leak",
                ) else "medium"
                hits.append({
                    "check": "input_pattern",
                    "category": category,
                    "description": description,
                    "matched_text": match.group()[:100],
                    "severity": severity,
                })

        return hits

    def check_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Check all user messages for injection patterns.

        Args:
            messages: List of {"role": str, "content": str} dicts.

        Returns:
            Combined hits from all user messages.
        """
        all_hits = []
        for msg in messages:
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if role == "user" and content and isinstance(content, str):
                hits = self.check_input(content)
                all_hits.extend(hits)

        return all_hits


# Global singleton
input_pattern_service = InputPatternMatcher()
