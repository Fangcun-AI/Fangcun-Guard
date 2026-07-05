"""
Diagnose answer match issue
Help users understand why the suggested answer does not answer according to the answer library
"""
import sys  # fcg-rewrite
import os  # fcg-rewrite

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # fcg-rewrite

from database.connection import get_db_session  # fcg-rewrite
from database.models import KnowledgeBase, Application  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

def diagnose_answer_match_issue():  # fcg-rewrite
    """Diagnose answer match issue"""
    db = get_db_session()  # fcg-rewrite
    try:
        # Get all knowledge bases
        kbs = db.query(KnowledgeBase).filter(KnowledgeBase.is_active == True).all()  # fcg-rewrite
        
        logger.info("=" * 80)  # fcg-rewrite
        logger.info("Rejection answer library matching diagnosis report")  # fcg-rewrite
        logger.info("=" * 80)  # fcg-rewrite
        
        # Group by application
        app_kb_map = {}  # fcg-rewrite
        global_kbs = []  # fcg-rewrite
        
        for kb in kbs:  # fcg-rewrite
            if kb.is_global:  # fcg-rewrite
                global_kbs.append(kb)  # fcg-rewrite
            else:
                app_id = str(kb.application_id) if kb.application_id else "No application ID"  # fcg-rewrite
                if app_id not in app_kb_map:  # fcg-rewrite
                    app_kb_map[app_id] = []  # fcg-rewrite
                app_kb_map[app_id].append(kb)  # fcg-rewrite
        
        # Display global knowledge base
        if global_kbs:  # fcg-rewrite
            logger.info("\n🌐 Global knowledge base (all applications available):")  # fcg-rewrite
            logger.info("-" * 80)  # fcg-rewrite
            for kb in global_kbs:  # fcg-rewrite
                logger.info(f"  📚 KB #{kb.id} - {kb.name}")  # fcg-rewrite
                logger.info(f"     Category: {kb.category}")  # fcg-rewrite
                logger.info(f"     Scanner: {kb.scanner_type}:{kb.scanner_identifier}")  # fcg-rewrite
                logger.info(f"     Threshold: {kb.similarity_threshold}")  # fcg-rewrite
                logger.info(f"     Application ID: {kb.application_id}")  # fcg-rewrite
        
        # Display each application's exclusive knowledge base
        if app_kb_map:  # fcg-rewrite
            logger.info("\n📱 Application exclusive knowledge base:")  # fcg-rewrite
            logger.info("-" * 80)  # fcg-rewrite
            for app_id, kb_list in app_kb_map.items():  # fcg-rewrite
                # Get application information
                app = db.query(Application).filter(Application.id == app_id).first()  # fcg-rewrite
                app_name = app.name if app else "Unknown application"  # fcg-rewrite
                
                logger.info(f"\n   Application: {app_name}")  # fcg-rewrite
                logger.info(f"   Application ID: {app_id}")  # fcg-rewrite
                logger.info(f"   Knowledge base number: {len(kb_list)}")  # fcg-rewrite
                
                for kb in kb_list:  # fcg-rewrite
                    logger.info(f"\n    📚 KB #{kb.id} - {kb.name}")  # fcg-rewrite
                    logger.info(f"        Category: {kb.category}")  # fcg-rewrite
                    logger.info(f"        Scanner: {kb.scanner_type}:{kb.scanner_identifier}")  # fcg-rewrite
                    logger.info(f"        Threshold: {kb.similarity_threshold}")  # fcg-rewrite
        
        logger.info("\n" + "=" * 80)  # fcg-rewrite
        logger.info("Problem diagnosis tips")  # fcg-rewrite
        logger.info("=" * 80)  # fcg-rewrite
        logger.info("\nIf the suggested answer does not answer according to the answer library, the possible reasons are:")  # fcg-rewrite
        logger.info("\n1. 🎯 Application ID mismatch")  # fcg-rewrite
        logger.info("   - The knowledge base is associated with a specific application, but the test is using a different application")  # fcg-rewrite
        logger.info("   - Solution: Ensure that the correct application is selected during online testing")  # fcg-rewrite
        logger.info("   - Or set the knowledge base to global (is_global=True)")  # fcg-rewrite
        
        logger.info("\n2. 🔍 Scanner identifier mismatch")  # fcg-rewrite
        logger.info("   - The knowledge base's scanner_type:scanner_identifier does not match the detected one")  # fcg-rewrite
        logger.info("   - Solution: Check if the knowledge base's scanner configuration is correct")  # fcg-rewrite
        
        logger.info("\n3. 📊 Similarity threshold too high")  # fcg-rewrite
        logger.info("   - The similarity between the user's question and the question in the knowledge base is below the threshold")  # fcg-rewrite
        logger.info("   - Solution: Lower the similarity threshold (e.g., from 0.9 to 0.7)")  # fcg-rewrite
        
        logger.info("\n4. ❌ Knowledge base not activated")  # fcg-rewrite
        logger.info("   - The knowledge base's is_active is False")  # fcg-rewrite
        logger.info("   - Solution: Activate the knowledge base")  # fcg-rewrite
        
        logger.info("\n5. 📝 Knowledge base content mismatch")  # fcg-rewrite
        logger.info("   - There is no question-answer pair in the knowledge base that is similar to the user's question")  # fcg-rewrite
        logger.info("   - Solution: Supplement the knowledge base content or check the vector file")  # fcg-rewrite
        
        logger.info("\n" + "=" * 80)  # fcg-rewrite
        logger.info("Next operation suggestions")  # fcg-rewrite
        logger.info("=" * 80)  # fcg-rewrite
        logger.info("\n1. Check online test logs: Check the application_id used during actual call")  # fcg-rewrite
        logger.info("   tail -f data/logs/detection.log | grep 'Knowledge base search'")  # fcg-rewrite
        
        logger.info("\n2. Test knowledge base search:")  # fcg-rewrite
        logger.info("   python scripts/test_kb_search.py --kb-id <Knowledge base ID> --query \"Your test question\"")  # fcg-rewrite
        
        logger.info("\n3. If the application ID mismatch, you can:")  # fcg-rewrite
        logger.info("   - Method A: Set the knowledge base to global (recommended)")  # fcg-rewrite
        logger.info("   - Method B: Ensure that the correct application is selected during testing")  # fcg-rewrite
        
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    diagnose_answer_match_issue()  # fcg-rewrite

