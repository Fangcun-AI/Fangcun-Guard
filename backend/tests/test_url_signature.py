from types import SimpleNamespace

import utils.url_signature as signatures


def setup_function():
    signatures.settings = SimpleNamespace(jwt_secret_key="secret")


def test_signature_round_trip_and_expiry():
    token, expires = signatures.generate_media_url_signature("tenant", "report.png", 60)
    assert signatures.verify_media_url_signature("tenant", "report.png", token, expires)
    assert not signatures.verify_media_url_signature("tenant", "other.png", token, expires)
    assert not signatures.verify_media_url_signature("tenant", "report.png", token, 0)


def test_signed_url_quotes_filename_path_segment():
    url = signatures.generate_signed_media_url("tenant", "folder/a b.png")
    assert "/tenant/folder%2Fa%20b.png?" in url
