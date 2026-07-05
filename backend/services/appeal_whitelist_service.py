import uuid
from typing import Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from database.models import Whitelist
from services.keyword_cache import keyword_cache
from utils.i18n_loader import get_translation


def t(language: str, key: str) -> str:
    return get_translation(language, "appealPage", key)


class AppealWhitelistService:
    """Maintains the dedicated whitelist used for approved appeals."""

    APPEAL_WHITELIST_NAME_EN = "False positive appeal whitelist"
    APPEAL_WHITELIST_NAME_ZH = "误报申诉白名单"

    async def add_to_appeal_whitelist(
        self,
        application_id: str,
        tenant_id: str,
        content: str,
        language: str,
        db: Session,
    ) -> Tuple[int, str]:
        app_uuid = uuid.UUID(application_id)
        tenant_uuid = uuid.UUID(tenant_id)

        keyword = content[:100].strip()
        if len(content) > 100:
            last_space = keyword.rfind(" ")
            if last_space > 50:
                keyword = keyword[:last_space]

        whitelist = db.query(Whitelist).filter(
            Whitelist.application_id == app_uuid,
            or_(
                Whitelist.name == self.APPEAL_WHITELIST_NAME_EN,
                Whitelist.name == self.APPEAL_WHITELIST_NAME_ZH,
            ),
        ).first()

        if whitelist:
            existing_keywords = whitelist.keywords if isinstance(whitelist.keywords, list) else []
            if keyword not in existing_keywords:
                existing_keywords.append(keyword)
                whitelist.keywords = existing_keywords
                flag_modified(whitelist, "keywords")
        else:
            whitelist = Whitelist(
                tenant_id=tenant_uuid,
                application_id=app_uuid,
                name=t(language, "whitelistName"),
                keywords=[keyword],
                description=t(language, "whitelistDescription"),
                is_active=True,
            )
            db.add(whitelist)

        db.commit()
        db.refresh(whitelist)
        await keyword_cache.invalidate_cache()
        return whitelist.id, keyword
