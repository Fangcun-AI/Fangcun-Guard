from types import SimpleNamespace

import utils.auth as auth


def setup_function():
    auth.settings = SimpleNamespace(
        super_admin_username="root",
        super_admin_password="secret",
        jwt_secret_key="jwt-secret",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=15,
    )


def test_api_key_keeps_public_prefix_and_length():
    key = auth.generate_api_key()
    assert key.startswith("sk-xxai-")
    assert len(key) == 60


def test_verify_user_token_preserves_legacy_user_id_alias():
    auth.jwt.decode = lambda *_args, **_kwargs: {"sub": "subject", "user_id": "tenant"}
    assert auth.verify_token("token") == {
        "tenant_id": "tenant",
        "user_id": "tenant",
        "sub": "subject",
        "email": None,
        "role": "user",
        "is_super_admin": False,
    }


def test_verify_admin_token_keeps_optional_identity_fields():
    auth.jwt.decode = lambda *_args, **_kwargs: {
        "sub": "root",
        "role": "admin",
        "tenant_id": "tenant",
        "email": "root@example.com",
    }
    assert auth.verify_token("token")["tenant_id"] == "tenant"
