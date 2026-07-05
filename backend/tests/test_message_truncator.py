from unittest.mock import patch

from models.requests import Message
from utils.message_truncator import MessageTrimmer


def test_trimmer_drops_leading_system_messages():
    messages = [
        Message(role="system", content="policy"),
        Message(role="user", content="question"),
    ]

    assert MessageTrimmer._drop_leading_non_user_messages(messages) == messages[1:]


def test_trimmer_keeps_recent_complete_pairs():
    messages = [
        Message(role="user", content="older"),
        Message(role="assistant", content="reply"),
        Message(role="user", content="old"),
        Message(role="assistant", content="answer"),
        Message(role="user", content="new question"),
    ]

    with patch("utils.message_truncator.settings.max_detection_context_length", 21):
        trimmed = MessageTrimmer.truncate_messages(messages)

    assert [message.content for message in trimmed] == ["old", "answer", "new question"]


def test_trimmer_samples_oversized_latest_user_message():
    messages = [Message(role="user", content="abcdefghij")]

    with (
        patch("utils.message_truncator.settings.max_detection_context_length", 4),
        patch("utils.message_truncator.random.randint", return_value=2),
    ):
        trimmed = MessageTrimmer.truncate_messages(messages)

    assert trimmed[0].content == "cdef"
