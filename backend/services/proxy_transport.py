"""Transport primitives for proxying completion requests to upstream models."""

import json  # fcg-rewrite
from typing import Any, Dict, List, Optional  # fcg-rewrite

import httpx  # fcg-rewrite

from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


class ProxyTransport:  # fcg-rewrite
    """Wrap the shared AsyncClient and request/response shaping rules."""

    def __init__(self, credential_cipher) -> None:  # fcg-rewrite
        self._credential_cipher = credential_cipher  # fcg-rewrite
        self._client = self._build_http_client()  # fcg-rewrite

    async def close(self) -> None:  # fcg-rewrite
        if self._client:  # fcg-rewrite
            await self._client.aclose()  # fcg-rewrite

    async def relay_streaming_chat_completion(self, model_config, request_data: Any, request_id: str):  # fcg-rewrite
        api_key = self._credential_cipher.decrypt(model_config.api_key_encrypted)  # fcg-rewrite
        payload = self._build_chat_payload(model_config, request_data, stream=True)  # fcg-rewrite
        headers = self._build_auth_headers(api_key)  # fcg-rewrite
        url = f"{model_config.api_base_url}/chat/completions"  # fcg-rewrite

        try:
            async with self._client.stream("POST", url, headers=headers, json=payload) as response:  # fcg-rewrite
                response.raise_for_status()  # fcg-rewrite
                async for line in response.aiter_lines():  # fcg-rewrite
                    if not line.strip():  # fcg-rewrite
                        continue  # fcg-rewrite
                    if line.startswith("data: "):  # fcg-rewrite
                        line = line[6:]  # fcg-rewrite
                    if line.strip() == "[DONE]":  # fcg-rewrite
                        break
                    try:
                        yield json.loads(line)  # fcg-rewrite
                    except json.JSONDecodeError:  # fcg-rewrite
                        continue  # fcg-rewrite
        except httpx.HTTPStatusError as exc:  # fcg-rewrite
            logger.error("HTTP error forwarding streaming to %s: %s", model_config.api_base_url, exc)  # fcg-rewrite
            try:
                error_detail = await exc.response.aread() if hasattr(exc.response, "aread") else str(exc)  # fcg-rewrite
                if isinstance(error_detail, bytes):  # fcg-rewrite
                    error_detail = error_detail.decode("utf-8", errors="ignore")  # fcg-rewrite
            except Exception:  # fcg-rewrite
                error_detail = f"Status code: {exc.response.status_code}"  # fcg-rewrite
            raise Exception(f"Model API streaming error: {error_detail}")  # fcg-rewrite
        except httpx.RequestError as exc:  # fcg-rewrite
            logger.error("Request error forwarding streaming to %s: %s", model_config.api_base_url, exc)  # fcg-rewrite
            raise Exception(f"Failed to connect to model API for streaming: {str(exc)}")  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("Unexpected error in streaming request: %s", exc)  # fcg-rewrite
            raise Exception(f"Streaming request failed: {str(exc)}")  # fcg-rewrite

    async def relay_chat_completion(  # fcg-rewrite
        self,
        model_config,  # fcg-rewrite
        request_data: Any,  # fcg-rewrite
        request_id: str,  # fcg-rewrite
        messages: Optional[list] = None,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        api_key = self._credential_cipher.decrypt(model_config.api_key_encrypted)  # fcg-rewrite
        payload = self._build_chat_payload(model_config, request_data, stream=None, messages=messages)  # fcg-rewrite
        url = f"{model_config.api_base_url}/chat/completions"  # fcg-rewrite
        result = await self._post_json(url, self._build_auth_headers(api_key), payload, model_config.api_base_url)  # fcg-rewrite
        if "id" not in result:  # fcg-rewrite
            result["id"] = f"chatcmpl-{request_id}"  # fcg-rewrite
        return result  # fcg-rewrite

    async def relay_completion(self, model_config, request_data: Any, request_id: str) -> Dict[str, Any]:  # fcg-rewrite
        api_key = self._credential_cipher.decrypt(model_config.api_key_encrypted)  # fcg-rewrite
        payload = self._build_completion_payload(model_config, request_data)  # fcg-rewrite
        url = f"{model_config.api_base_url}/completions"  # fcg-rewrite
        result = await self._post_json(url, self._build_auth_headers(api_key), payload, model_config.api_base_url)  # fcg-rewrite
        if "id" not in result:  # fcg-rewrite
            result["id"] = f"cmpl-{request_id}"  # fcg-rewrite
        return result  # fcg-rewrite

    async def dispatch_upstream_gateway(  # fcg-rewrite
        self,
        api_config,  # fcg-rewrite
        model_name: str,  # fcg-rewrite
        messages: List[Dict],  # fcg-rewrite
        stream: bool = False,  # fcg-rewrite
        temperature: Optional[float] = None,  # fcg-rewrite
        max_tokens: Optional[int] = None,  # fcg-rewrite
        top_p: Optional[float] = None,  # fcg-rewrite
        frequency_penalty: Optional[float] = None,  # fcg-rewrite
        presence_penalty: Optional[float] = None,  # fcg-rewrite
        stop: Optional[List[str]] = None,  # fcg-rewrite
        extra_body: Optional[Dict[str, Any]] = None,  # fcg-rewrite
    ):
        api_key = self._credential_cipher.decrypt(api_config.api_key_encrypted)  # fcg-rewrite
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"  # fcg-rewrite
        logger.info(  # fcg-rewrite
            "Calling upstream API %s with upstream_api_config_id=%s, api_key=%s",  # fcg-rewrite
            api_config.api_base_url,  # fcg-rewrite
            api_config.id,  # fcg-rewrite
            masked_key,  # fcg-rewrite
        )

        payload = {  # fcg-rewrite
            "model": model_name,  # fcg-rewrite
            "messages": messages,  # fcg-rewrite
            "stream": stream,  # fcg-rewrite
        }
        optional_values = {  # fcg-rewrite
            "temperature": temperature,  # fcg-rewrite
            "max_tokens": max_tokens,  # fcg-rewrite
            "top_p": top_p,  # fcg-rewrite
            "frequency_penalty": frequency_penalty,  # fcg-rewrite
            "presence_penalty": presence_penalty,  # fcg-rewrite
            "stop": stop,  # fcg-rewrite
        }
        for key, value in optional_values.items():  # fcg-rewrite
            if value is not None:  # fcg-rewrite
                payload[key] = value  # fcg-rewrite

        self._merge_extra_body(payload, extra_body)  # fcg-rewrite
        logger.info("Upstream payload being sent: %s", json.dumps(payload, ensure_ascii=False))  # fcg-rewrite

        url = f"{api_config.api_base_url}/chat/completions"  # fcg-rewrite
        headers = self._build_auth_headers(api_key)  # fcg-rewrite
        try:
            if stream:  # fcg-rewrite
                return self._client.stream("POST", url, headers=headers, json=payload)  # fcg-rewrite
            response = await self._client.post(url, headers=headers, json=payload)  # fcg-rewrite
            response.raise_for_status()  # fcg-rewrite
            response_json = response.json()  # fcg-rewrite
            logger.info(  # fcg-rewrite
                "Upstream response received: %s",  # fcg-rewrite
                json.dumps(response_json, ensure_ascii=False)[:2000],  # fcg-rewrite
            )
            return response_json  # fcg-rewrite
        except httpx.HTTPStatusError as exc:  # fcg-rewrite
            self._raise_upstream_error(exc, api_config.api_base_url, "calling gateway upstream")  # fcg-rewrite
        except httpx.RequestError as exc:  # fcg-rewrite
            logger.error("Request error calling gateway upstream %s: %s", api_config.api_base_url, exc)  # fcg-rewrite
            raise Exception("Failed to connect to upstream API")  # fcg-rewrite

    def _build_http_client(self) -> httpx.AsyncClient:  # fcg-rewrite
        limits = httpx.Limits(  # fcg-rewrite
            max_keepalive_connections=50,  # fcg-rewrite
            max_connections=200,  # fcg-rewrite
            keepalive_expiry=30.0,  # fcg-rewrite
        )
        timeout = httpx.Timeout(connect=15.0, read=600.0, write=15.0, pool=10.0)  # fcg-rewrite
        return httpx.AsyncClient(limits=limits, timeout=timeout, http2=True, verify=True)  # fcg-rewrite

    def _build_auth_headers(self, api_key: str) -> Dict[str, str]:  # fcg-rewrite
        return {  # fcg-rewrite
            "Authorization": f"Bearer {api_key}",  # fcg-rewrite
            "Content-Type": "application/json",  # fcg-rewrite
        }

    def _build_chat_payload(  # fcg-rewrite
        self,
        model_config,  # fcg-rewrite
        request_data: Any,  # fcg-rewrite
        *,
        stream: Optional[bool],  # fcg-rewrite
        messages: Optional[list] = None,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        payload = request_data.dict(exclude_unset=True)  # fcg-rewrite
        payload["model"] = model_config.model_name  # fcg-rewrite
        payload["messages"] = (  # fcg-rewrite
            messages  # fcg-rewrite
            if messages is not None  # fcg-rewrite
            else [{"role": msg.role, "content": msg.content} for msg in request_data.messages]  # fcg-rewrite
        )
        if stream is not None:  # fcg-rewrite
            payload["stream"] = stream  # fcg-rewrite
        self._merge_extra_body(payload, getattr(request_data, "extra_body", None))  # fcg-rewrite
        return payload  # fcg-rewrite

    def _build_completion_payload(self, model_config, request_data: Any) -> Dict[str, Any]:  # fcg-rewrite
        payload = {  # fcg-rewrite
            "model": model_config.model_name,  # fcg-rewrite
            "prompt": request_data.prompt,  # fcg-rewrite
        }
        optional_params = [  # fcg-rewrite
            "temperature",  # fcg-rewrite
            "top_p",  # fcg-rewrite
            "n",
            "stream",  # fcg-rewrite
            "logprobs",  # fcg-rewrite
            "echo",
            "stop",
            "max_tokens",  # fcg-rewrite
            "presence_penalty",  # fcg-rewrite
            "frequency_penalty",  # fcg-rewrite
            "best_of",  # fcg-rewrite
            "logit_bias",  # fcg-rewrite
            "user",
        ]
        for param in optional_params:  # fcg-rewrite
            value = getattr(request_data, param, None)  # fcg-rewrite
            if value is not None:  # fcg-rewrite
                payload[param] = value  # fcg-rewrite
            elif hasattr(model_config, param) and getattr(model_config, param):  # fcg-rewrite
                if param in ["temperature", "top_p", "frequency_penalty", "presence_penalty"]:  # fcg-rewrite
                    payload[param] = float(getattr(model_config, param))  # fcg-rewrite
                elif param == "max_tokens":  # fcg-rewrite
                    payload[param] = model_config.max_tokens  # fcg-rewrite
        self._merge_extra_body(payload, getattr(request_data, "extra_body", None))  # fcg-rewrite
        return payload  # fcg-rewrite

    def _merge_extra_body(self, payload: Dict[str, Any], extra_body: Optional[Dict[str, Any]]) -> None:  # fcg-rewrite
        if not extra_body:  # fcg-rewrite
            return
        for key, value in extra_body.items():  # fcg-rewrite
            if key != "xxai_app_user_id":  # fcg-rewrite
                payload[key] = value  # fcg-rewrite

    async def _post_json(  # fcg-rewrite
        self,
        url: str,  # fcg-rewrite
        headers: Dict[str, str],  # fcg-rewrite
        payload: Dict[str, Any],  # fcg-rewrite
        target_label: str,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        try:
            response = await self._client.post(url, headers=headers, json=payload)  # fcg-rewrite
            response.raise_for_status()  # fcg-rewrite
            return response.json()  # fcg-rewrite
        except httpx.HTTPStatusError as exc:  # fcg-rewrite
            self._raise_upstream_error(exc, target_label, "forwarding to")  # fcg-rewrite
        except httpx.RequestError as exc:  # fcg-rewrite
            logger.error("Request error forwarding to %s: %s", target_label, exc)  # fcg-rewrite
            raise Exception("Failed to connect to model API")  # fcg-rewrite

    def _raise_upstream_error(self, exc: httpx.HTTPStatusError, target_label: str, action: str) -> None:  # fcg-rewrite
        logger.error("HTTP error %s %s: %s", action, target_label, exc)  # fcg-rewrite
        if hasattr(exc, "response"):  # fcg-rewrite
            logger.error("Upstream API response: %s", exc.response.text)  # fcg-rewrite
        if exc.response.status_code == 401:  # fcg-rewrite
            raise Exception("Invalid API credentials")  # fcg-rewrite
        if exc.response.status_code == 403:  # fcg-rewrite
            raise Exception("Access forbidden by upstream API")  # fcg-rewrite
        if exc.response.status_code == 429:  # fcg-rewrite
            raise Exception("Rate limit exceeded")  # fcg-rewrite
        if exc.response.status_code >= 500:  # fcg-rewrite
            raise Exception("Upstream API service unavailable")  # fcg-rewrite
        raise Exception("Request failed")  # fcg-rewrite
