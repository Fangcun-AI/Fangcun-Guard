import asyncio
import pickle
from datetime import timezone

from services.log_to_db_service import AuditLogWriter


def test_count_lines_ignores_blank_lines(tmp_path):
    path = tmp_path / "detection_20260101.jsonl"
    path.write_text('{"id": 1}\n\n{"id": 2}\n')
    assert AuditLogWriter()._count_lines(path) == 2


def test_legacy_set_state_is_reset(tmp_path):
    async def exercise():
        path = tmp_path / "state.pkl"
        path.write_bytes(pickle.dumps({"legacy-file"}))
        writer = AuditLogWriter()
        writer._state_file = path
        await writer._load_processed_files_state()
        assert writer.processed_files == {}

    asyncio.run(exercise())


def test_uuid_parser_rejects_invalid_identifier():
    assert AuditLogWriter._uuid("not-a-uuid") is None


def test_timestamp_parser_accepts_zulu_suffix():
    parsed = AuditLogWriter._timestamp("2026-01-02T03:04:05Z")
    assert parsed.tzinfo == timezone.utc
