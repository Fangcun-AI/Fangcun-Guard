import json

from services.segmentation_service import SegmentationService


def test_short_payload_is_left_intact():
    service = SegmentationService(max_segment_size=20)

    segments = service.segment_content("short text", "plain_text", {})

    assert [segment.content for segment in segments] == ["short text"]


def test_json_array_chunks_remain_valid_json():
    service = SegmentationService(max_segment_size=24)
    payload = json.dumps([{"id": 1}, {"id": 2}, {"id": 3}])

    segments = service.segment_content(payload, "json", {})

    assert len(segments) > 1
    assert [item for segment in segments for item in json.loads(segment.content)] == [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]


def test_csv_chunks_repeat_the_header():
    service = SegmentationService(max_segment_size=30)
    payload = "email,name\na@example.com,A\nb@example.com,B"

    segments = service.segment_content(payload, "csv", {})

    assert len(segments) == 2
    assert all(segment.content.startswith("email,name\n") for segment in segments)


def test_markdown_chunks_on_sections():
    service = SegmentationService(max_segment_size=16)
    payload = "# One\nfirst\n\n# Two\nsecond"

    segments = service.segment_content(payload, "markdown", {})

    assert [segment.content for segment in segments] == ["# One\nfirst", "# Two\nsecond"]
