from datetime import datetime
from types import SimpleNamespace

import utils.email as email_service


class FakeSMTP:
    instances = []

    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.started_tls = False
        self.login_args = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def starttls(self):
        self.started_tls = True

    def login(self, *args):
        self.login_args = args

    def send_message(self, message):
        self.message = message


def setup_function():
    FakeSMTP.instances.clear()
    email_service.settings = SimpleNamespace(
        smtp_server="smtp.example.com",
        smtp_port=587,
        smtp_username="sender@example.com",
        smtp_password="secret",
        smtp_use_tls=True,
        smtp_use_ssl=False,
    )
    email_service.smtplib.SMTP = FakeSMTP
    email_service.smtplib.SMTP_SSL = FakeSMTP
    email_service.get_translation = lambda language, *keys: f"{language}:{keys[-1]}"


def test_generate_verification_code_uses_requested_digit_length():
    code = email_service.generate_verification_code(9)
    assert len(code) == 9
    assert code.isdigit()


def test_password_reset_template_escapes_link_attribute():
    _, html = email_service.get_password_reset_email_template("en", 'https://example.com/?x="><script>')
    assert "<script>" not in html
    assert "&quot;&gt;&lt;script&gt;" in html


def test_send_verification_email_uses_tls_transport():
    assert email_service.send_verification_email("user@example.com", "123456")
    smtp = FakeSMTP.instances[0]
    assert smtp.started_tls
    assert smtp.login_args == ("sender@example.com", "secret")
    assert smtp.message["To"] == "user@example.com"


def test_appeal_template_escapes_content_and_truncates_preview():
    _, html = email_service.get_appeal_review_email_template(
        "zh",
        {"original_content": "<script>alert(1)</script>", "original_categories": ["prompt"]},
        {"recent_requests": [{"content": "x" * 110}]},
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert f"{'x' * 100}..." in html


def test_expiry_helpers_keep_original_durations():
    now = datetime.utcnow()
    assert 599 <= (email_service.get_verification_expiry() - now).total_seconds() <= 601
    assert 3599 <= (email_service.get_reset_token_expiry() - now).total_seconds() <= 3601
