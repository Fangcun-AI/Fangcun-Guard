#!/usr/bin/env python3
"""
Fix response templates for S8 and S10 categories

This script fixes the incorrect template content for:
- S8 (Hate & Discrimination)
- S10 (Profanity)

Both were incorrectly set to the same content with mixed Chinese/English.
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
import json  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

# Correct templates as JSON
CORRECT_TEMPLATES = {  # fcg-rewrite
    'S8': {
        'en': "I'm sorry, but I cannot engage with content containing hate speech or discrimination.",  # fcg-rewrite
        'zh': "抱歉，我无法处理包含仇恨言论或歧视的内容。"  # fcg-rewrite
    },
    'S10': {  # fcg-rewrite
        'en': "I'm sorry, but I cannot respond to profanity or offensive language.",  # fcg-rewrite
        'zh': "抱歉，我无法回应脏话或冒犯性语言。"  # fcg-rewrite
    }
}

def fix_templates():  # fcg-rewrite
    """Fix the incorrect template content for S8 and S10"""
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("开始修复 S8 和 S10 响应模板...")  # fcg-rewrite

            # Fix S8 templates
            logger.info("修复 S8 (Hate & Discrimination) 模板...")  # fcg-rewrite
            s8_json = json.dumps(CORRECT_TEMPLATES['S8'])  # fcg-rewrite

            result = conn.execute(text("""
                UPDATE response_templates
                SET template_content = :content
                WHERE category = 'S8' AND is_active = true
            """), {'content': s8_json})

            s8_count = result.rowcount  # fcg-rewrite
            logger.info(f"更新了 {s8_count} 个 S8 模板")  # fcg-rewrite

            # Fix S10 templates
            logger.info("修复 S10 (Profanity) 模板...")  # fcg-rewrite
            s10_json = json.dumps(CORRECT_TEMPLATES['S10'])  # fcg-rewrite

            result = conn.execute(text("""
                UPDATE response_templates
                SET template_content = :content
                WHERE category = 'S10' AND is_active = true
            """), {'content': s10_json})

            s10_count = result.rowcount  # fcg-rewrite
            logger.info(f"更新了 {s10_count} 个 S10 模板")  # fcg-rewrite

            # Verify the changes
            logger.info("验证更新结果...")  # fcg-rewrite

            for category, template in CORRECT_TEMPLATES.items():  # fcg-rewrite
                result = conn.execute(text("""
                    SELECT template_content, tenant_id, is_default
                    FROM response_templates
                    WHERE category = :category AND is_active = true
                    ORDER BY is_default
                """), {'category': category})

                templates = result.fetchall()  # fcg-rewrite
                logger.info(f"\n=== {category} 模板更新后内容 ===")  # fcg-rewrite
                for tmpl in templates:  # fcg-rewrite
                    logger.info(f"Tenant: {tmpl[1]}, Default: {tmpl[2]}")  # fcg-rewrite
                    logger.info(f"Content: {tmpl[0]}")  # fcg-rewrite
                    logger.info("---")  # fcg-rewrite

            conn.commit()  # fcg-rewrite
            logger.info("✅ S8 和 S10 模板修复完成!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"❌ 修复模板时出错: {e}")  # fcg-rewrite
            raise

def check_current_templates():  # fcg-rewrite
    """Check current template content before fixing"""
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("=== 检查当前 S8 和 S10 模板内容 ===")  # fcg-rewrite

            for category in ['S8', 'S10']:  # fcg-rewrite
                result = conn.execute(text("""
                    SELECT template_content, tenant_id, is_default
                    FROM response_templates
                    WHERE category = :category AND is_active = true
                    ORDER BY is_default
                """), {'category': category})

                templates = result.fetchall()  # fcg-rewrite
                logger.info(f"\n--- 当前 {category} 模板 ---")  # fcg-rewrite
                for tmpl in templates:  # fcg-rewrite
                    logger.info(f"Tenant: {tmpl[1]}, Default: {tmpl[2]}")  # fcg-rewrite
                    logger.info(f"Content: {tmpl[0]}")  # fcg-rewrite
                    if "Everyone deserves" in str(tmpl[0]) or "平等对待" in str(tmpl[0]):  # fcg-rewrite
                        logger.warning("⚠️  发现问题的模板内容!")  # fcg-rewrite
                    logger.info("---")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            logger.error(f"检查模板时出错: {e}")  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    import argparse  # fcg-rewrite

    parser = argparse.ArgumentParser(description="修复 S8 和 S10 响应模板")  # fcg-rewrite
    parser.add_argument("--check", action="store_true", help="只检查当前模板，不修复")  # fcg-rewrite
    parser.add_argument("--fix", action="store_true", help="执行修复")  # fcg-rewrite

    args = parser.parse_args()  # fcg-rewrite

    if args.check:  # fcg-rewrite
        check_current_templates()  # fcg-rewrite
    elif args.fix:  # fcg-rewrite
        check_current_templates()  # fcg-rewrite
        print("\n" + "="*50)  # fcg-rewrite
        fix_templates()  # fcg-rewrite
        print("\n修复完成! 请重启服务以使更改生效。")  # fcg-rewrite
    else:
        print("请使用 --check 检查或 --fix 修复模板")  # fcg-rewrite
        print("例如: python fix_response_templates.py --check")  # fcg-rewrite
        print("      python fix_response_templates.py --fix")  # fcg-rewrite