"""Validated base64 image handling for guarded requests."""

import base64
import binascii
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from config import settings
from utils.logger import setup_logger

logger = setup_logger()
_DATA_URL = re.compile(r"^data:image/([a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_EXTENSIONS = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "gif": "gif", "webp": "webp"}


class ImageHelpers:
    @staticmethod
    def is_base64_image(url: str) -> bool:
        return bool(_DATA_URL.match(url))

    @staticmethod
    def extract_base64_data(url: str) -> Tuple[Optional[str], Optional[bytes]]:
        match = _DATA_URL.match(url)
        if not match:
            logger.error("Invalid base64 image data URL")
            return None, None
        image_format = match.group(1).lower()
        if image_format not in _EXTENSIONS:
            logger.error(f"Unsupported image format: {image_format}")
            return None, None
        try:
            return image_format, base64.b64decode(match.group(2), validate=True)
        except (ValueError, binascii.Error) as exc:
            logger.error(f"Invalid base64 image payload: {exc}")
            return None, None

    @staticmethod
    def save_base64_image(url: str, tenant_id: str) -> Optional[str]:
        image_format, content = ImageHelpers.extract_base64_data(url)
        if not image_format or not content:
            return None
        try:
            root = Path(settings.media_dir).resolve()
            directory = (root / tenant_id).resolve()
            if root not in directory.parents:
                raise ValueError("tenant media directory escapes configured root")
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{uuid.uuid4().hex}.{_EXTENSIONS[image_format]}"
            path.write_bytes(content)
            logger.info(f"Saved base64 image: {path} ({len(content)} bytes)")
            return str(path)
        except Exception as exc:
            logger.error(f"Failed to save base64 image: {exc}")
            return None

    @staticmethod
    def process_image_url(
        url: str, tenant_id: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        if not ImageHelpers.is_base64_image(url):
            raise ValueError("Only base64 encoded image data URLs are supported")
        image_format, content = ImageHelpers.extract_base64_data(url)
        if not image_format or content is None:
            raise ValueError("Invalid or unsupported base64 image")
        saved_path = ImageHelpers.save_base64_image(url, tenant_id) if tenant_id else None
        return url, saved_path

    @staticmethod
    def encode_file_to_base64(file_bytes: bytes, image_format: str = "jpeg") -> str:
        image_format = image_format.lower()
        if image_format not in _EXTENSIONS:
            raise ValueError(f"Unsupported image format: {image_format}")
        encoded = base64.b64encode(file_bytes).decode("ascii")
        return f"data:image/{image_format};base64,{encoded}"

    @staticmethod
    def validate_image_size(base64_url: str, max_size_mb: int = 10) -> bool:
        _, content = ImageHelpers.extract_base64_data(base64_url)
        return content is not None and len(content) <= max_size_mb * 1024 * 1024


image_utils = ImageHelpers()
