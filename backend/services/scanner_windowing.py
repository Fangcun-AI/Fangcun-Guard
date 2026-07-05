import math
from itertools import product
from typing import Dict, List, Tuple

from config import settings
from utils.logger import setup_logger

logger = setup_logger()

TextWindow = Tuple[str, int, int]


def _text_content(message: Dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


class SlidingWindowProcessor:
    """Build bounded text windows for prompt and response inspection."""

    def __init__(
        self,
        max_context_length: int = None,
        max_windows: int = None,
        max_pairs: int = None,
        overlap_ratio: float = 0.2,
    ):
        self.max_context_length = max_context_length or settings.max_detection_context_length
        self.max_windows = max_windows or settings.scanner_window_max_windows
        self.max_pairs = max_pairs or settings.scanner_window_max_pairs
        self.overlap_ratio = overlap_ratio

    def _downsample_windows(
        self, windows: List[TextWindow], target_count: int
    ) -> List[TextWindow]:
        if target_count <= 0 or len(windows) <= target_count:
            return windows
        sampled = [windows[int(index * len(windows) / target_count)] for index in range(target_count)]
        sampled[-1] = windows[-1]
        return sampled

    def _create_windows(self, text: str, window_size: int) -> List[TextWindow]:
        window_size = max(1, window_size)
        if not text or len(text) <= window_size:
            return [(text, 0, len(text))]

        step_size = max(1, int(window_size * (1 - self.overlap_ratio)))
        windows = []
        start = 0
        while start < len(text):
            end = min(start + window_size, len(text))
            windows.append((text[start:end], start, end))
            if end == len(text):
                break
            start += step_size
        return windows

    def get_message_windows(self, messages: List[Dict]) -> List[List[Dict]]:
        if not messages:
            return [[]]
        user_messages = [message for message in messages if message.get("role") == "user"]
        assistant_messages = [
            message for message in messages if message.get("role") == "assistant"
        ]
        user_text = "\n".join(_text_content(message) for message in user_messages)
        assistant_text = "\n".join(_text_content(message) for message in assistant_messages)
        if len(user_text) + len(assistant_text) <= self.max_context_length:
            return [messages]

        if not assistant_messages:
            windows = self._create_windows(user_text, self.max_context_length)
            windows = self._downsample_windows(windows, self.max_windows)
            return [[{"role": "user", "content": text}] for text, _, _ in windows]

        half_context = max(1, self.max_context_length // 2)
        user_windows = self._downsample_windows(
            self._create_windows(user_text, half_context), self.max_windows
        )
        assistant_windows = self._downsample_windows(
            self._create_windows(assistant_text, half_context), self.max_windows
        )
        if len(user_windows) * len(assistant_windows) > self.max_pairs:
            user_target = min(len(user_windows), max(1, int(math.sqrt(self.max_pairs))))
            assistant_target = min(
                len(assistant_windows), max(1, self.max_pairs // user_target)
            )
            user_windows = self._downsample_windows(user_windows, user_target)
            assistant_windows = self._downsample_windows(assistant_windows, assistant_target)

        return [
            [
                {"role": "user", "content": user_window[0]},
                {"role": "assistant", "content": assistant_window[0]},
            ]
            for user_window, assistant_window in product(user_windows, assistant_windows)
        ]
