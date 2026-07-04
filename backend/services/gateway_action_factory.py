import json
from typing import Any, Dict


class GatewayActionFactory:
    """Builds gateway action payloads in a consistent wire format."""

    def create_block_response(
        self,
        request_id: str,
        reason: str,
        message: str,
        detection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "action": "block",
            "request_id": request_id,
            "detection_result": detection_result,
            "block_response": {
                "code": 200,
                "content_type": "application/json",
                "body": json.dumps({
                    "id": f"chatcmpl-blocked-{request_id}",
                    "object": "chat.completion",
                    "model": "fangcunguard-security",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": message,
                        },
                        "finish_reason": "content_filter",
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }),
            },
        }

    def create_replace_response(
        self,
        request_id: str,
        message: str,
        detection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "action": "replace",
            "request_id": request_id,
            "detection_result": detection_result,
            "replace_response": {
                "code": 200,
                "content_type": "application/json",
                "body": json.dumps({
                    "id": f"chatcmpl-replaced-{request_id}",
                    "object": "chat.completion",
                    "model": "fangcunguard-security",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": message,
                        },
                        "finish_reason": "content_filter",
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }),
            },
        }
