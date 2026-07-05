"""
Rebuild knowledge base vector index
Fix missing or damaged vector files
"""
import sys  # fcg-rewrite
import os  # fcg-rewrite

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # fcg-rewrite

import glob  # fcg-rewrite
from pathlib import Path  # fcg-rewrite
from database.connection import get_db_session  # fcg-rewrite
from database.models import KnowledgeBase  # fcg-rewrite
from services.knowledge_base_service import knowledge_base_service  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

def rebuild_vectors():  # fcg-rewrite
    """Rebuild all missing vector files"""
    db = get_db_session()  # fcg-rewrite
    try:
        # Get all knowledge bases
        knowledge_bases = db.query(KnowledgeBase).all()  # fcg-rewrite
        
        logger.info(f"Found {len(knowledge_bases)} knowledge bases in database")  # fcg-rewrite
        
        rebuilt_count = 0  # fcg-rewrite
        skipped_count = 0  # fcg-rewrite
        error_count = 0  # fcg-rewrite
        
        for kb in knowledge_bases:  # fcg-rewrite
            kb_id = kb.id  # fcg-rewrite
            kb_name = kb.name  # fcg-rewrite
            
            # Check if vector file exists
            vector_file = knowledge_base_service.storage_path / f"kb_{kb_id}_vectors.pkl"  # fcg-rewrite
            
            if vector_file.exists():  # fcg-rewrite
                logger.info(f"KB #{kb_id} ({kb_name}): Vector file already exists, skipping")  # fcg-rewrite
                skipped_count += 1  # fcg-rewrite
                continue  # fcg-rewrite
            
            # Find original file
            pattern = str(knowledge_base_service.storage_path / f"kb_{kb_id}_*.jsonl*")  # fcg-rewrite
            original_files = glob.glob(pattern)  # fcg-rewrite
            
            if not original_files:  # fcg-rewrite
                logger.warning(f"KB #{kb_id} ({kb_name}): No original file found, skipping")  # fcg-rewrite
                error_count += 1  # fcg-rewrite
                continue  # fcg-rewrite
            
            # Use the first matching file
            original_file = Path(original_files[0])  # fcg-rewrite
            logger.info(f"KB #{kb_id} ({kb_name}): Found original file {original_file.name}")  # fcg-rewrite
            
            try:
                # Read original file
                with open(original_file, 'rb') as f:  # fcg-rewrite
                    file_content = f.read()  # fcg-rewrite
                
                # Parse JSONL
                logger.info(f"KB #{kb_id} ({kb_name}): Parsing JSONL...")  # fcg-rewrite
                qa_pairs = knowledge_base_service.parse_jsonl_file(file_content)  # fcg-rewrite
                logger.info(f"KB #{kb_id} ({kb_name}): Parsed {len(qa_pairs)} QA pairs")  # fcg-rewrite
                
                # Create vector index
                logger.info(f"KB #{kb_id} ({kb_name}): Creating vector index...")  # fcg-rewrite
                vector_file_path = knowledge_base_service.create_vector_index(qa_pairs, kb_id)  # fcg-rewrite
                logger.info(f"KB #{kb_id} ({kb_name}): ✅ Vector index created at {vector_file_path}")  # fcg-rewrite
                
                rebuilt_count += 1  # fcg-rewrite
                
            except Exception as e:  # fcg-rewrite
                logger.error(f"KB #{kb_id} ({kb_name}): ❌ Failed to rebuild: {e}")  # fcg-rewrite
                error_count += 1  # fcg-rewrite
                continue  # fcg-rewrite
        
        # Print summary
        logger.info("=" * 60)  # fcg-rewrite
        logger.info("Rebuild Summary:")  # fcg-rewrite
        logger.info(f"  Total knowledge bases: {len(knowledge_bases)}")  # fcg-rewrite
        logger.info(f"  ✅ Successfully rebuilt: {rebuilt_count}")  # fcg-rewrite
        logger.info(f"  ⏭️  Skipped (already exist): {skipped_count}")  # fcg-rewrite
        logger.info(f"  ❌ Failed: {error_count}")  # fcg-rewrite
        logger.info("=" * 60)  # fcg-rewrite
        
    except Exception as e:  # fcg-rewrite
        logger.error(f"Fatal error: {e}")  # fcg-rewrite
        raise
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    logger.info("Starting knowledge base vector rebuild...")  # fcg-rewrite
    rebuild_vectors()  # fcg-rewrite
    logger.info("Done!")  # fcg-rewrite

