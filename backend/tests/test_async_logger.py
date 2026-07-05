import asyncio
import json

import services.async_logger as async_logger


class FakeFile:
    def __init__(self):
        self.content = ""
        self.closed = False

    async def write(self, content):
        self.content += content

    async def flush(self):
        pass

    async def close(self):
        self.closed = True


def test_logger_writes_queued_event_before_stop(tmp_path):
    async def exercise():
        target = FakeFile()

        async def open_file(*_args, **_kwargs):
            return target

        async_logger.aiofiles.open = open_file
        async_logger.clean_detection_data = lambda value: value
        recorder = async_logger.AsyncDetectionRecorder(str(tmp_path))
        await recorder.log_detection({"request_id": "request-1"})
        await recorder.stop()
        event = json.loads(target.content)
        assert event["request_id"] == "request-1"
        assert "logged_at" in event
        assert target.closed

    asyncio.run(exercise())


def test_get_log_files_applies_date_range(tmp_path):
    for date in ("20260101", "20260102", "20260103"):
        tmp_path.joinpath(f"detection_{date}.jsonl").touch()
    recorder = async_logger.AsyncDetectionRecorder(str(tmp_path))
    assert [path.name for path in recorder.get_log_files(("20260102", "20260102"))] == [
        "detection_20260102.jsonl"
    ]
