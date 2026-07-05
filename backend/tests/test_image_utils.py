from pathlib import Path
from types import SimpleNamespace

import utils.image_utils as images


def setup_function():
    images.settings = SimpleNamespace(media_dir="/tmp/fangcun-image-tests")


def test_encode_and_extract_image_round_trip():
    url = images.ImageHelpers.encode_file_to_base64(b"content", "png")
    assert images.ImageHelpers.extract_base64_data(url) == ("png", b"content")


def test_extract_rejects_invalid_payload_and_unsupported_format():
    assert images.ImageHelpers.extract_base64_data("data:image/png;base64,%%%") == (None, None)
    assert images.ImageHelpers.extract_base64_data("data:image/svg+xml;base64,PHN2Zz4=") == (None, None)


def test_save_rejects_tenant_directory_escape(tmp_path):
    images.settings.media_dir = str(tmp_path)
    url = images.ImageHelpers.encode_file_to_base64(b"content", "png")
    assert images.ImageHelpers.save_base64_image(url, "../escape") is None
    assert not Path(tmp_path).parent.joinpath("escape").exists()
