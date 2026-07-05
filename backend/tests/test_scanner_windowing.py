from services.scanner_windowing import SlidingWindowProcessor


def test_short_messages_are_not_rewritten():
    messages = [{"role": "user", "content": "short"}]

    assert SlidingWindowProcessor(max_context_length=20).get_message_windows(messages) == [
        messages
    ]


def test_tiny_windows_always_advance():
    processor = SlidingWindowProcessor(
        max_context_length=1, max_windows=10, max_pairs=4
    )

    assert processor._create_windows("abc", 1) == [
        ("a", 0, 1),
        ("b", 1, 2),
        ("c", 2, 3),
    ]


def test_user_only_windows_are_capped_and_keep_last_window():
    processor = SlidingWindowProcessor(
        max_context_length=4, max_windows=2, max_pairs=4, overlap_ratio=0
    )

    windows = processor.get_message_windows([{"role": "user", "content": "abcdefghij"}])

    assert len(windows) == 2
    assert windows[-1][0]["content"] == "ij"


def test_cross_product_windows_respect_pair_limit():
    processor = SlidingWindowProcessor(
        max_context_length=4, max_windows=10, max_pairs=4, overlap_ratio=0
    )

    windows = processor.get_message_windows(
        [
            {"role": "user", "content": "abcdefgh"},
            {"role": "assistant", "content": "ABCDEFGH"},
        ]
    )

    assert len(windows) <= 4
    assert all([message["role"] for message in pair] == ["user", "assistant"] for pair in windows)
