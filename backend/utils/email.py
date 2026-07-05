import secrets
import smtplib
import string
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from config import settings
from utils.i18n_loader import get_translation


def generate_verification_code(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _text(value, fallback: str = "") -> str:
    return escape(str(fallback if value in (None, "") else value), quote=True)


def _translation(language: str, section: str, key: str) -> str:
    return _text(get_translation(language, "email", section, key))


def _page(platform: str, title: str, content: str, accent: str = "#1890ff") -> str:
    return (
        '<html><body><div style="font-family:Arial,sans-serif;max-width:800px;margin:auto">'
        f'<header style="background:{accent};padding:20px;text-align:center">'
        f'<h1 style="color:white;margin:0">{platform}</h1></header>'
        f'<main style="padding:24px 20px"><h2>{title}</h2>{content}</main>'
        "</div></body></html>"
    )


def _message(recipient: str, subject: str, html_body: str) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.smtp_username
    message["To"] = recipient
    message.attach(MIMEText(html_body, "html", "utf-8"))
    return message


def _deliver(recipient: str, subject: str, html_body: str) -> None:
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_server, settings.smtp_port) as server:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(_message(recipient, subject, html_body))


def _send(recipient: str, subject: str, html_body: str, error_label: str) -> bool:
    try:
        _deliver(recipient, subject, html_body)
        return True
    except Exception as exc:
        print(f"Failed to send {error_label} email: {exc}")
        return False


def _require_smtp() -> None:
    if not settings.smtp_username or not settings.smtp_password:
        raise Exception("SMTP configuration is not set")


def get_email_template(language: str, verification_code: str) -> tuple[str, str]:
    section = "verification"
    subject = _translation(language, section, "subject")
    content = (
        f"<p>{_translation(language, section, 'greeting')}</p>"
        f"<p>{_translation(language, section, 'codePrompt')}</p>"
        '<p style="margin:28px;text-align:center">'
        f'<strong style="background:#1890ff;color:white;padding:14px 28px;'
        f'font-size:24px;letter-spacing:5px">{_text(verification_code)}</strong></p>'
        f"<p>{_translation(language, section, 'validityNote')}</p>"
        f"<hr><small>{_translation(language, section, 'footer')}</small>"
    )
    return subject, _page(
        _translation(language, section, "platformName"),
        _translation(language, section, "title"),
        content,
    )


def send_verification_email(email: str, verification_code: str, language: str = "en") -> bool:
    _require_smtp()
    subject, html_body = get_email_template(language, verification_code)
    return _send(email, subject, html_body, "verification")


def get_verification_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=10)


def get_password_reset_email_template(language: str, reset_url: str) -> tuple[str, str]:
    section = "passwordReset"
    subject = _translation(language, section, "subject")
    content = (
        f"<p>{_translation(language, section, 'greeting')}</p>"
        f"<p>{_translation(language, section, 'instruction')}</p>"
        '<p style="margin:28px;text-align:center">'
        f'<a href="{_text(reset_url)}" style="background:#1890ff;color:white;'
        f'padding:14px 28px;text-decoration:none">{_translation(language, section, "buttonText")}</a></p>'
        f"<small>{_translation(language, section, 'validityNote')}</small>"
        f"<p><small>{_translation(language, section, 'ignoreNote')}</small></p>"
        f"<hr><small>{_translation(language, section, 'footer')}</small>"
    )
    return subject, _page(
        _translation(language, section, "platformName"),
        _translation(language, section, "title"),
        content,
    )


def send_password_reset_email(email: str, reset_url: str, language: str = "en") -> bool:
    _require_smtp()
    subject, html_body = get_password_reset_email_template(language, reset_url)
    return _send(email, subject, html_body, "password reset")


def get_reset_token_expiry() -> datetime:
    return datetime.utcnow() + timedelta(hours=1)


def _appeal_history(user_context: dict, language: str) -> str:
    bans = user_context.get("ban_history") or []
    if not bans:
        return _translation(language, "appealReview", "noBanHistory")
    items = []
    for ban in bans:
        status = "Active" if ban.get("is_active") else "Expired"
        items.append(
            f"<li>{_text(ban.get('banned_at'), 'N/A')} - {_text(ban.get('reason'), 'No reason')} "
            f"(Risk: {_text(ban.get('risk_level'), 'N/A')}, Status: {status})</li>"
        )
    return f"<ul>{''.join(items)}</ul>"


def _appeal_requests(user_context: dict, language: str) -> str:
    requests = user_context.get("recent_requests") or []
    if not requests:
        return _translation(language, "appealReview", "noRecentRequests")
    items = []
    for request in requests:
        preview = str(request.get("content", "N/A"))
        if len(preview) > 100:
            preview = f"{preview[:100]}..."
        items.append(
            f"<li>[{_text(request.get('created_at'), 'N/A')}] {_text(preview)}<br>"
            f"Security={_text(request.get('security_risk'), 'N/A')}, "
            f"Compliance={_text(request.get('compliance_risk'), 'N/A')}, "
            f"Data={_text(request.get('data_risk'), 'N/A')} | "
            f"Action: {_text(request.get('action'), 'N/A')}</li>"
        )
    return f"<ol>{''.join(items)}</ol>"


def get_appeal_review_email_template(
    language: str,
    appeal_data: dict,
    user_context: dict,
) -> tuple[str, str]:
    section = "appealReview"
    label = lambda key: _translation(language, section, key)
    categories = ", ".join(map(str, appeal_data.get("original_categories") or [])) or "None"
    original_content = str(appeal_data.get("original_content", ""))
    if len(original_content) > 500:
        original_content = f"{original_content[:500]}..."
    ai_result = "Approved" if appeal_data.get("ai_approved") else "Rejected (Considered True Positive)"
    content = (
        f"<p>{label('greeting')}</p>"
        f"<p><b>{label('requestIdLabel')}:</b> {_text(appeal_data.get('request_id'), 'N/A')}<br>"
        f"<b>{label('appealUserLabel')}:</b> {_text(appeal_data.get('user_id'), 'Anonymous')}<br>"
        f"<b>{label('riskLevelLabel')}:</b> {_text(appeal_data.get('original_risk_level'), 'N/A')}<br>"
        f"<b>{label('riskCategoriesLabel')}:</b> {_text(categories)}</p>"
        f"<h3>{label('originalContentLabel')}</h3><pre>{_text(original_content)}</pre>"
        f"<h3>{label('aiReviewLabel')}</h3><p><b>{label('aiReviewLabel')}:</b> {ai_result}<br>"
        f"<b>{label('aiReasonLabel')}:</b> {_text(appeal_data.get('ai_review_result'), 'No reason provided')}</p>"
        f"<h3>{label('userCredibilityLabel')}</h3><h4>{label('banHistoryLabel')}</h4>"
        f"{_appeal_history(user_context, language)}"
        f"<h3>{label('recentRequestsLabel')}</h3>{_appeal_requests(user_context, language)}"
        f"<p><b>{label('actionInstruction')}</b></p><hr><small>{label('footer')}</small>"
    )
    return label("subject"), _page(label("platformName"), label("title"), content, "#fa8c16")


def send_appeal_review_email(
    to_email: str,
    appeal_data: dict,
    user_context: dict,
    language: str = "zh",
) -> bool:
    if not settings.smtp_username or not settings.smtp_password:
        print("SMTP configuration is not set, skipping email")
        return False
    subject, html_body = get_appeal_review_email_template(language, appeal_data, user_context)
    return _send(to_email, subject, html_body, "appeal review")
