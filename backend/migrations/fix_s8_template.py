#!/usr/bin/env python3
"""
Fix S8 (Hate & Discrimination) response template
修复 S8 (歧视性内容) 响应模板

Update the template to use the correct rejection message.
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import text  # fcg-rewrite
from database.connection import engine, get_db_session  # fcg-rewrite
from database.models import ResponseTemplate  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
import json  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

# Correct template for S8
CORRECT_S8_TEMPLATE = {  # fcg-rewrite
    'en': "Request blocked by FangcunGuard due to content potentially involving hate and discrimination.",  # fcg-rewrite
    'zh': "请求已被FangcunGuard拦截，原因：可能涉及仇恨与歧视。"  # fcg-rewrite
}

def fix_s8_template():  # fcg-rewrite
    """Fix the S8 template content"""
    db = get_db_session()  # fcg-rewrite
    try:
        logger.info("开始修复 S8 (Hate & Discrimination) 响应模板...")  # fcg-rewrite

        # Find all S8 templates
        s8_templates = db.query(ResponseTemplate).filter_by(  # fcg-rewrite
            category='S8',  # fcg-rewrite
            is_active=True  # fcg-rewrite
        ).all()

        if not s8_templates:  # fcg-rewrite
            logger.warning("未找到 S8 模板，创建新的全局默认模板...")  # fcg-rewrite
            
            # Create a new global default S8 template
            new_template = ResponseTemplate(  # fcg-rewrite
                tenant_id=None,  # Global template  # fcg-rewrite
                category='S8',  # fcg-rewrite
                template_content=CORRECT_S8_TEMPLATE,  # fcg-rewrite
                is_default=True,  # fcg-rewrite
                is_active=True  # fcg-rewrite
            )
            db.add(new_template)  # fcg-rewrite
            db.commit()  # fcg-rewrite
            logger.info(f"✅ 创建了新的 S8 全局默认模板")  # fcg-rewrite
        else:
            logger.info(f"找到 {len(s8_templates)} 个 S8 模板")  # fcg-rewrite
            updated_count = 0  # fcg-rewrite
            
            for tmpl in s8_templates:  # fcg-rewrite
                old_content = tmpl.template_content  # fcg-rewrite
                logger.info(f"\n模板 ID: {tmpl.id}")  # fcg-rewrite
                logger.info(f"  Tenant: {tmpl.tenant_id}")  # fcg-rewrite
                logger.info(f"  Is Default: {tmpl.is_default}")  # fcg-rewrite
                logger.info(f"  旧内容: {old_content}")  # fcg-rewrite
                
                # Update the template
                tmpl.template_content = CORRECT_S8_TEMPLATE  # fcg-rewrite
                updated_count += 1  # fcg-rewrite
                
                logger.info(f"  新内容: {CORRECT_S8_TEMPLATE}")  # fcg-rewrite
                logger.info(f"  ✅ 已更新")  # fcg-rewrite
            
            db.commit()  # fcg-rewrite
            logger.info(f"\n✅ 成功更新了 {updated_count} 个 S8 模板!")  # fcg-rewrite

        # Verify the changes
        logger.info("\n=== 验证更新结果 ===")  # fcg-rewrite
        s8_templates = db.query(ResponseTemplate).filter_by(  # fcg-rewrite
            category='S8',  # fcg-rewrite
            is_active=True  # fcg-rewrite
        ).all()

        for tmpl in s8_templates:  # fcg-rewrite
            logger.info(f"\n模板 ID: {tmpl.id}")  # fcg-rewrite
            logger.info(f"  Tenant: {tmpl.tenant_id}")  # fcg-rewrite
            logger.info(f"  Is Default: {tmpl.is_default}")  # fcg-rewrite
            logger.info(f"  内容: {tmpl.template_content}")  # fcg-rewrite

        logger.info("\n✅ S8 模板修复完成!")  # fcg-rewrite
        
        # Invalidate template cache to force reload
        logger.info("\n刷新模板缓存...")  # fcg-rewrite
        try:
            from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite
            import asyncio  # fcg-rewrite
            asyncio.run(enhanced_template_service.invalidate_cache())  # fcg-rewrite
            logger.info("✅ 模板缓存已刷新")  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            logger.warning(f"缓存刷新失败（需要手动重启服务）: {e}")  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        logger.error(f"修复 S8 模板时出错: {e}", exc_info=True)  # fcg-rewrite
        raise
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    fix_s8_template()  # fcg-rewrite

