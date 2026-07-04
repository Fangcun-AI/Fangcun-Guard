"""Public false-positive appeal result page."""

from html import escape
import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from services.appeal_service import appeal_service
from utils.i18n_loader import get_translation


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["appeal"])

_STATUS_STYLE = {
    "approved": ("success", "&#10004;", "statusApproved"),
    "rejected": ("rejected", "&#10008;", "statusRejected"),
    "pending_review": ("pending", "&#128100;", "statusPendingReview"),
    "reviewing": ("pending", "&#8987;", "statusProcessing"),
    "pending": ("pending", "&#8987;", "statusProcessing"),
}
_PAGE_STYLE = """
*{box-sizing:border-box}body{align-items:center;background:linear-gradient(135deg,#667eea,#764ba2);
display:flex;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;justify-content:center;
margin:0;min-height:100vh;padding:20px}.card{background:#fff;border-radius:16px;box-shadow:0 10px 40px
rgba(0,0,0,.2);max-width:500px;padding:40px;text-align:center;width:100%}.icon{font-size:64px}
.title{font-size:24px;font-weight:600;margin:8px}.message{color:#374151;line-height:1.6}
.success .icon,.success .title{color:#10b981}.rejected .icon,.rejected .title{color:#ef4444}
.pending .icon,.pending .title{color:#f59e0b}.error .icon,.error .title{color:#6b7280}
.detail{background:#f9fafb;border-radius:8px;margin-top:20px;padding:16px;text-align:left}
.reviewer{background:#eff6ff;border:1px solid #bfdbfe}.detail h3{font-size:14px;margin:0 0 8px}
.detail p{font-size:14px;line-height:1.6;margin:0;white-space:pre-wrap}.hint{background:#f3f4f6;
border-radius:8px;color:#6b7280;font-size:14px;margin-top:24px;padding:12px}.footer{border-top:1px
solid #e5e7eb;color:#9ca3af;font-size:12px;margin-top:24px;padding-top:16px}
"""


def detect_language(request: Request) -> str:
    return "zh" if "zh" in request.headers.get("accept-language", "en").lower() else "en"


def _translation(language: str, key: str) -> str:
    return escape(get_translation(language, "appealPage", key))


def _detail(title: str, content: object, extra_class: str = "") -> str:
    if not content:
        return ""
    return f'<section class="detail {extra_class}"><h3>{title}</h3><p>{escape(str(content))}</p></section>'


def generate_result_html(result: dict, language: str = "zh") -> str:
    status = str(result.get("status", ""))
    if result.get("success") and status != "approved":
        state = ("success", "&#10004;", "statusProcessing")
    else:
        state = _STATUS_STYLE.get(status, ("error", "&#9888;", "statusFailed"))
    style, icon, title_key = state
    reviewer = result.get("final_reviewer_email") if status == "pending_review" else None
    return f"""<!doctype html>
<html lang="{'zh-CN' if language == 'zh' else 'en'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_translation(language, 'title')} - FangcunGuard</title><style>{_PAGE_STYLE}</style></head>
<body><main class="card {style}"><div class="icon">{icon}</div>
<div class="title">{_translation(language, title_key)}</div>
<div class="message">{escape(str(result.get('message', '')))}</div>
{_detail(_translation(language, 'reviewDetails'), result.get('reason'))}
{_detail(_translation(language, 'finalReviewer'), reviewer, 'reviewer')}
<div class="hint">{_translation(language, 'closeHint')}</div>
<div class="footer">{_translation(language, 'poweredBy')}</div></main></body></html>"""


@router.get("/appeal/{request_id}", response_class=HTMLResponse)
async def process_appeal(request_id: str, request: Request, lang: Optional[str] = None):
    language = lang if lang in {"zh", "en"} else detect_language(request)
    ip_address = request.client.host if request.client else None
    logger.info("processing appeal request_id=%s ip=%s lang=%s", request_id, ip_address, language)
    try:
        result = await appeal_service.process_appeal(
            request_id=request_id,
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
            language=language,
        )
    except Exception as exc:
        logger.error("appeal processing error: %s", exc)
        result = {"success": False, "error": "system_error", "message": get_translation(language, "appealPage", "systemError")}
    return HTMLResponse(content=generate_result_html(result, language))
