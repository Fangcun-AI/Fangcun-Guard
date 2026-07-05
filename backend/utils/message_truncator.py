"""Conversation sampling for bounded-cost guardrail inspection."""

from __future__ import annotations

import random
from typing import Any, List, Sequence

from config import settings
from models.requests import Message


class MessageTrimmer:
    """Keep the newest valid conversation tail within the detection budget."""

    @staticmethod
    def calculate_total_content_length(messages: Sequence[Message]) -> int:
        return sum(MessageTrimmer._content_length(message.content) for message in messages)

    @staticmethod
    def get_random_window(content: str, max_length: int) -> str:
        if max_length <= 0:
            return ""
        if len(content) <= max_length:
            return content
        start = random.randint(0, len(content) - max_length)
        return content[start : start + max_length]

    @classmethod
    def truncate_messages(cls, messages: List[Message]) -> List[Message]:
        conversation = cls._drop_leading_non_user_messages(messages)
        if not conversation:
            return []

        budget = settings.max_detection_context_length
        if cls.calculate_total_content_length(conversation) <= budget:
            return conversation

        if conversation[-1].role == "assistant":
            return cls._fit_assistant_tail(conversation, budget)
        return cls._fit_user_tail(conversation, budget)

    @classmethod
    def _fit_user_tail(cls, messages: Sequence[Message], budget: int) -> List[Message]:
        newest = messages[-1]
        newest_size = cls._content_length(newest.content)
        if newest_size > budget:
            return [cls._trimmed_copy(newest, budget)]

        return cls._prepend_complete_pairs(
            messages[:-1],
            [newest],
            remaining_budget=budget - newest_size,
        )

    @classmethod
    def _fit_assistant_tail(cls, messages: Sequence[Message], budget: int) -> List[Message]:
        assistant = messages[-1]
        user_index = next(
            (index for index in range(len(messages) - 2, -1, -1) if messages[index].role == "user"),
            None,
        )
        if user_index is None:
            return []

        user = messages[user_index]
        assistant_size = cls._content_length(assistant.content)
        user_size = cls._content_length(user.content)
        if assistant_size >= budget:
            user_budget = min(user_size, budget // 3)
            assistant_budget = budget - user_budget
            return [
                cls._trimmed_copy(user, user_budget),
                cls._trimmed_copy(assistant, assistant_budget),
            ]

        pair_size = user_size + assistant_size
        if pair_size > budget:
            return [cls._trimmed_copy(user, budget - assistant_size), assistant]

        return cls._prepend_complete_pairs(
            messages[:user_index],
            [user, assistant],
            remaining_budget=budget - pair_size,
        )

    @classmethod
    def _prepend_complete_pairs(
        cls,
        history: Sequence[Message],
        tail: List[Message],
        *,
        remaining_budget: int,
    ) -> List[Message]:
        result = list(tail)
        index = len(history) - 1
        while index >= 0:
            if (
                index > 0
                and history[index].role == "assistant"
                and history[index - 1].role == "user"
            ):
                pair = [history[index - 1], history[index]]
                pair_size = cls.calculate_total_content_length(pair)
                if pair_size > remaining_budget:
                    break
                result[0:0] = pair
                remaining_budget -= pair_size
                index -= 2
                continue

            if index == 0 and history[index].role == "user":
                message_size = cls._content_length(history[index].content)
                if message_size <= remaining_budget:
                    result.insert(0, history[index])
            index -= 1
        return result

    @staticmethod
    def _drop_leading_non_user_messages(messages: Sequence[Message]) -> List[Message]:
        first_user_index = next(
            (index for index, message in enumerate(messages) if message.role == "user"),
            None,
        )
        return list(messages[first_user_index:]) if first_user_index is not None else []

    @staticmethod
    def _trimmed_copy(message: Message, budget: int) -> Message:
        if isinstance(message.content, str):
            content: Any = MessageTrimmer.get_random_window(message.content, budget)
        elif isinstance(message.content, list):
            content = message.content[: max(budget, 0)]
        else:
            content = message.content
        return Message(role=message.role, content=content)

    @staticmethod
    def _content_length(content: Any) -> int:
        if content is None:
            return 0
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(
                len(part.text or "")
                + len(part.image_url.url if getattr(part, "image_url", None) else "")
                for part in content
            )
        return len(str(content))
