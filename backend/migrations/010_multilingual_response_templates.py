"""
Migration 010: Convert response template content to multilingual JSON format

Issue: template_content is currently TEXT, needs to support multiple languages
Solution: Convert template_content to JSON format: {"en": "...", "zh": "...", ...}
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import text  # fcg-rewrite
from database.connection import engine  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

# Default multilingual templates for each category
# Format: "Request blocked by FangcunGuard due to content potentially involving [topic]."
DEFAULT_TEMPLATES = {  # fcg-rewrite
    'S1': {
        'en': "Request blocked by FangcunGuard due to content potentially involving general political topics.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及一般政治话题。"  # fcg-rewrite
    },
    'S2': {
        'en': "Request blocked by FangcunGuard due to content potentially involving sensitive political topics.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及敏感政治话题。"  # fcg-rewrite
    },
    'S3': {
        'en': "Request blocked by FangcunGuard due to content potentially involving insult to national symbols or leaders.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及侮辱国家象征或领导人。"  # fcg-rewrite
    },
    'S4': {
        'en': "Request blocked by FangcunGuard due to content potentially involving harm to minors.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及伤害未成年人。"  # fcg-rewrite
    },
    'S5': {
        'en': "Request blocked by FangcunGuard due to content potentially involving violent crime.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及暴力犯罪。"  # fcg-rewrite
    },
    'S6': {
        'en': "Request blocked by FangcunGuard due to content potentially involving non-violent crime.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及非暴力犯罪。"  # fcg-rewrite
    },
    'S7': {
        'en': "Request blocked by FangcunGuard due to content potentially involving pornography.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及色情内容。"  # fcg-rewrite
    },
    'S8': {
        'en': "Request blocked by FangcunGuard due to content potentially involving hate and discrimination.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及仇恨与歧视。"  # fcg-rewrite
    },
    'S9': {
        'en': "Request blocked by FangcunGuard due to content potentially involving prompt injection attacks.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及提示词注入攻击。"  # fcg-rewrite
    },
    'S10': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving profanity.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及辱骂。"  # fcg-rewrite
    },
    'S11': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving privacy invasion.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及侵犯个人隐私。"  # fcg-rewrite
    },
    'S12': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving commercial violations.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及商业违法违规。"  # fcg-rewrite
    },
    'S13': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving intellectual property infringement.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及侵犯知识产权。"  # fcg-rewrite
    },
    'S14': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving harassment.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及骚扰。"  # fcg-rewrite
    },
    'S15': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving weapons of mass destruction.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及大规模杀伤性武器。"  # fcg-rewrite
    },
    'S16': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving self-harm.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及自我伤害。"  # fcg-rewrite
    },
    'S17': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving sexual crimes.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及性犯罪。"  # fcg-rewrite
    },
    'S18': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving threats.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及威胁。"  # fcg-rewrite
    },
    'S19': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving professional financial advice.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及专业金融建议。"  # fcg-rewrite
    },
    'S20': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving professional medical advice.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及专业医疗建议。"  # fcg-rewrite
    },
    'S21': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content potentially involving professional legal advice.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：可能涉及专业法律建议。"  # fcg-rewrite
    },
    'default': {  # fcg-rewrite
        'en': "Request blocked by FangcunGuard due to content policy violation.",  # fcg-rewrite
        'zh': "请求已被FangcunGuard拦截，原因：违反内容政策。"  # fcg-rewrite
    }
}

def upgrade():  # fcg-rewrite
    """
    Convert template_content from TEXT to JSON format
    """
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Starting migration 010: Convert response templates to multilingual JSON format")  # fcg-rewrite

            # Step 1: Create a temporary column for new JSON data
            logger.info("Adding temporary column template_content_json...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE response_templates
                ADD COLUMN IF NOT EXISTS template_content_json JSONB
            """))
            conn.commit()  # fcg-rewrite

            # Step 2: Migrate existing data
            logger.info("Migrating existing template content to JSON format...")  # fcg-rewrite

            # Get all existing templates
            result = conn.execute(text("""
                SELECT id, category, template_content
                FROM response_templates
            """))

            templates = result.fetchall()  # fcg-rewrite

            for template in templates:  # fcg-rewrite
                template_id, category, old_content = template  # fcg-rewrite

                # Determine if content is in English or Chinese based on content
                # If content contains Chinese characters, treat as Chinese, otherwise English
                is_chinese = any('\u4e00' <= char <= '\u9fff' for char in str(old_content))  # fcg-rewrite

                # Get default templates for this category
                default_template = DEFAULT_TEMPLATES.get(category, DEFAULT_TEMPLATES['default'])  # fcg-rewrite

                # Create multilingual content
                if is_chinese:  # fcg-rewrite
                    # Original content is Chinese, use default English
                    new_content = {  # fcg-rewrite
                        'en': default_template['en'],  # fcg-rewrite
                        'zh': old_content  # fcg-rewrite
                    }
                else:
                    # Original content is English, use default Chinese
                    new_content = {  # fcg-rewrite
                        'en': old_content,  # fcg-rewrite
                        'zh': default_template['zh']  # fcg-rewrite
                    }

                # Update the row with JSON content
                import json  # fcg-rewrite
                json_str = json.dumps(new_content).replace("'", "''")  # Escape single quotes for SQL  # fcg-rewrite
                conn.execute(  # fcg-rewrite
                    text(f"""
                        UPDATE response_templates
                        SET template_content_json = '{json_str}'::jsonb
                        WHERE id = {template_id}
                    """)
                )

            conn.commit()  # fcg-rewrite
            logger.info(f"Migrated {len(templates)} templates to JSON format")  # fcg-rewrite

            # Step 3: Drop old column and rename new column
            logger.info("Replacing old template_content column with JSON version...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE response_templates
                DROP COLUMN template_content
            """))

            conn.execute(text("""
                ALTER TABLE response_templates
                RENAME COLUMN template_content_json TO template_content
            """))

            # Step 4: Add NOT NULL constraint
            conn.execute(text("""
                ALTER TABLE response_templates
                ALTER COLUMN template_content SET NOT NULL
            """))

            conn.commit()  # fcg-rewrite
            logger.info("Migration 010 completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Migration 010 failed: {e}")  # fcg-rewrite
            raise

def downgrade():  # fcg-rewrite
    """
    Revert JSON format back to TEXT (uses English content only)
    """
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Starting downgrade of migration 010")  # fcg-rewrite
            logger.warning("Downgrading will lose multilingual support and keep English content only!")  # fcg-rewrite

            # Step 1: Create temporary TEXT column
            logger.info("Adding temporary column template_content_text...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE response_templates
                ADD COLUMN IF NOT EXISTS template_content_text TEXT
            """))
            conn.commit()  # fcg-rewrite

            # Step 2: Extract English content from JSON
            logger.info("Extracting English content from JSON...")  # fcg-rewrite
            conn.execute(text("""
                UPDATE response_templates
                SET template_content_text = template_content->>'en'
            """))
            conn.commit()  # fcg-rewrite

            # Step 3: Drop JSON column and rename text column
            logger.info("Replacing JSON column with TEXT column...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE response_templates
                DROP COLUMN template_content
            """))

            conn.execute(text("""
                ALTER TABLE response_templates
                RENAME COLUMN template_content_text TO template_content
            """))

            # Step 4: Add NOT NULL constraint
            conn.execute(text("""
                ALTER TABLE response_templates
                ALTER COLUMN template_content SET NOT NULL
            """))

            conn.commit()  # fcg-rewrite
            logger.info("Migration 010 downgrade completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Migration 010 downgrade failed: {e}")  # fcg-rewrite
            raise

if __name__ == "__main__":  # fcg-rewrite
    import sys  # fcg-rewrite

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":  # fcg-rewrite
        downgrade()  # fcg-rewrite
    else:
        upgrade()  # fcg-rewrite
