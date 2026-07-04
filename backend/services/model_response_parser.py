import math
from typing import Optional, Tuple


class ModelResponseParser:
    """Extracts normalized content and confidence/sensitivity from model responses."""

    def extract_content(self, result_data: dict) -> str:
        return result_data["choices"][0]["message"]["content"].strip()

    def extract_first_token_probability(self, result_data: dict) -> Optional[float]:
        choice = result_data["choices"][0]
        logprobs = choice.get("logprobs")
        if not logprobs:
            return None
        content = logprobs.get("content")
        if not content:
            return None
        first_token_logprob = content[0]["logprob"]
        return math.exp(first_token_logprob)

    def extract_content_and_probability(self, result_data: dict) -> Tuple[str, Optional[float]]:
        return self.extract_content(result_data), self.extract_first_token_probability(result_data)
