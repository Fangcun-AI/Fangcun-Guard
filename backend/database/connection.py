"""Database engines, sessions, and idempotent startup initialization."""

import asyncio
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from config import settings

_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
    "pool_timeout": 30,
    "echo": False,
}


def _engine(pool_size: int, max_overflow: int):
    return create_engine(
        settings.database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        **_ENGINE_OPTIONS,
    )


detection_engine = _engine(8, 8)
admin_engine = _engine(10, 20)
proxy_engine = _engine(3, 5)
engine = detection_engine

DetectionSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=detection_engine)
AdminSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=admin_engine)
ProxySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=proxy_engine)
SessionLocal = DetectionSessionLocal
Base = declarative_base()


def get_database_url():
    return settings.database_url


def _yield_session(factory):
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_db():
    yield from _yield_session(SessionLocal)


def get_admin_db():
    yield from _yield_session(AdminSessionLocal)


def get_proxy_db():
    yield from _yield_session(ProxySessionLocal)


def get_db_session():
    return SessionLocal()


def get_detection_db_session():
    return DetectionSessionLocal()


def get_admin_db_session():
    return AdminSessionLocal()


def get_proxy_db_session():
    return ProxySessionLocal()


def create_detection_engine():
    return detection_engine


def create_admin_engine():
    return admin_engine


def create_proxy_engine():
    return proxy_engine


def _reset_schema(connection) -> None:
    try:
        for table in ("proxy_configs", "email_verifications", "user_switches"):
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        Base.metadata.drop_all(bind=connection)
    except Exception:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO public"))


def _seed_defaults(db: Session) -> None:
    from database.models import ResponseTemplate, SystemConfig

    if db.query(SystemConfig).filter_by(config_key="initialized").first():
        return
    db.add(SystemConfig(config_key="initialized", config_value="true", description="System initialization flag"))
    db.add(SystemConfig(config_key="default_action", config_value="reject", description="Default action for high risk content"))
    responses = {
        "S1": "I'm sorry, I can't discuss political topics.",
        "S2": "I'm sorry, I can't answer questions involving sensitive political topics.",
        "S3": "I'm sorry, I can't answer questions that may damage national image.",
        "S4": "I'm sorry, I can't provide content that may harm minors.",
        "S5": "I'm sorry, I can't answer questions involving violent crime.",
        "S6": "I'm sorry, I can't provide content involving illegal activities.",
        "S7": "I'm sorry, I can't provide content involving pornography.",
        "S8": "I'm sorry, but I cannot engage with content containing hate speech or discrimination.",
        "S9": "I'm sorry, I can't answer questions involving prompt injection attacks.",
        "S10": "I'm sorry, but I cannot respond to profanity or offensive language.",
        "S11": "I'm sorry, I can't discuss content involving personal privacy. Please respect others' privacy.",
        "S12": "I'm sorry, I can't provide advice on possible business violations. Please consult with a professional.",
        "default": "I'm sorry, I can't answer this question. Please contact customer service if you have any questions.",
    }
    for category, content in responses.items():
        db.add(ResponseTemplate(category=category, risk_level="high_risk", template_content=content, is_default=True))
    db.commit()


def _run_migrations(logger) -> None:
    path = Path(__file__).parent.parent / "migrations" / "run_migrations.py"
    if not path.exists():
        logger.warning("Migrations directory not found, skipping migrations")
        return
    try:
        spec = importlib.util.spec_from_file_location("run_migrations", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        executed, failed = module.run_migrations(dry_run=False)
        logger.info("Database migrations completed: executed=%s failed=%s", executed, failed)
    except Exception as error:
        logger.error("Failed to run migrations: %s", error)


def _load_builtin_scanners(logger) -> None:
    from services.builtin_scanner_loader import load_builtin_scanner_packages

    db = AdminSessionLocal()
    try:
        summary = load_builtin_scanner_packages(db)
        logger.info("Built-in scanner packages ensured: %s", summary)
    except FileNotFoundError as error:
        logger.warning("Built-in scanners directory missing: %s", error)
    finally:
        db.close()


async def init_db(minimal=False):
    """Create tables once per deployment process group and load control-plane defaults."""
    import database.models  # noqa: F401
    from services.admin_service import admin_service
    from utils.logger import setup_logger

    logger = setup_logger()
    selected_engine = detection_engine if minimal else admin_engine
    lock_key = 0x5A6F_5858_4941_4752
    with selected_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        acquired = lock.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key}).scalar()
        if not acquired:
            logger.info("Another process is initializing the database")
            await asyncio.sleep(2)
            try:
                with selected_engine.connect() as verify:
                    verify.execute(text("SELECT 1 FROM tenants LIMIT 1"))
            except Exception as error:
                logger.warning("Database initialization is still in progress: %s", error)
                await asyncio.sleep(3)
            return
        try:
            with selected_engine.begin() as connection:
                if settings.reset_database_on_startup:
                    _reset_schema(connection)
                Base.metadata.create_all(bind=connection)
                if not minimal:
                    db = Session(bind=connection)
                    admin_service.seed_super_admin(db)
                    _seed_defaults(db)
            if not minimal:
                _run_migrations(logger)
                _load_builtin_scanners(logger)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
