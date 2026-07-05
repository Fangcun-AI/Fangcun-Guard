"""
Knowledge base diagnostic tool
Check if knowledge base configurations and search functions are normal
"""
import sys  # fcg-rewrite
import os  # fcg-rewrite

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # fcg-rewrite

from database.connection import get_db_session  # fcg-rewrite
from database.models import KnowledgeBase  # fcg-rewrite
from services.knowledge_base_service import knowledge_base_service  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

def diagnose_knowledge_bases():  # fcg-rewrite
    """Diagnose all knowledge bases"""
    db = get_db_session()  # fcg-rewrite
    try:
        knowledge_bases = db.query(KnowledgeBase).all()  # fcg-rewrite
        
        logger.info("=" * 80)  # fcg-rewrite
        logger.info("Knowledge base diagnosis report")  # fcg-rewrite
        logger.info("=" * 80)  # fcg-rewrite
        
        issues = []  # fcg-rewrite
        warnings = []  # fcg-rewrite
        
        for kb in knowledge_bases:  # fcg-rewrite
            logger.info(f"\nKB #{kb.id} - {kb.name} (Category: {kb.category})")  # fcg-rewrite
            logger.info("-" * 80)  # fcg-rewrite
            
            # Check if activated
            if not kb.is_active:  # fcg-rewrite
                issue = f"KB #{kb.id} ({kb.name}) not activated"  # fcg-rewrite
                logger.error(f"  ❌ {issue}")  # fcg-rewrite
                issues.append(issue)  # fcg-rewrite
            else:
                logger.info(f"  ✅ Activated")  # fcg-rewrite
            
            # Check if similarity threshold is too high
            if kb.similarity_threshold > 0.8:  # fcg-rewrite
                warning = f"KB #{kb.id} ({kb.name}) similarity threshold too high ({kb.similarity_threshold})"  # fcg-rewrite
                logger.warning(f"  ⚠️  {warning}")  # fcg-rewrite
                warnings.append(warning)  # fcg-rewrite
            else:
                logger.info(f"  ✅ Similarity threshold: {kb.similarity_threshold}")  # fcg-rewrite
            
            # Check if vector file exists
            vector_file = knowledge_base_service.storage_path / f"kb_{kb.id}_vectors.pkl"  # fcg-rewrite
            if not vector_file.exists():  # fcg-rewrite
                issue = f"KB #{kb.id} ({kb.name}) vector file not exists"  # fcg-rewrite
                logger.error(f"  ❌ {issue}")  # fcg-rewrite
                issues.append(issue)  # fcg-rewrite
            else:
                file_info = knowledge_base_service.get_file_info(kb.id)  # fcg-rewrite
                logger.info(f"  ✅ Vector file exists ({file_info['total_qa_pairs']} QA pairs)")  # fcg-rewrite
            
            # Check if it is a global knowledge base
            if kb.is_global:  # fcg-rewrite
                logger.info(f"  🌐 Global knowledge base")  # fcg-rewrite
            else:
                logger.info(f"  📱 Application knowledge base (App ID: {kb.application_id})")  # fcg-rewrite
        
        # Print summary
        logger.info("\n" + "=" * 80)  # fcg-rewrite
        logger.info("Diagnosis summary")  # fcg-rewrite
        logger.info("=" * 80)  # fcg-rewrite
        
        if not issues and not warnings:  # fcg-rewrite
            logger.info("✅ All knowledge base configurations are normal!")  # fcg-rewrite
        else:
            if issues:  # fcg-rewrite
                logger.error(f"\n❌ Found {len(issues)} issues:")  # fcg-rewrite
                for issue in issues:  # fcg-rewrite
                    logger.error(f"  - {issue}")  # fcg-rewrite
            
            if warnings:  # fcg-rewrite
                logger.warning(f"\n⚠️  Found {len(warnings)} warnings:")  # fcg-rewrite
                for warning in warnings:  # fcg-rewrite
                    logger.warning(f"  - {warning}")  # fcg-rewrite
        
        logger.info("\nTips:")  # fcg-rewrite
        logger.info("  - Run fix_knowledge_base_config.py to automatically fix configuration issues")  # fcg-rewrite
        logger.info("  - Run rebuild_knowledge_base_vectors.py to rebuild missing vector files")  # fcg-rewrite
        logger.info("  - Run test_kb_search.py to test search functionality")  # fcg-rewrite
        
    except Exception as e:  # fcg-rewrite
        logger.error(f"Diagnosis failed: {e}")  # fcg-rewrite
        raise
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    diagnose_knowledge_bases()  # fcg-rewrite

