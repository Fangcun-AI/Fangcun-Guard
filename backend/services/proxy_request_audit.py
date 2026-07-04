"""Audit log persistence for proxy and gateway calls."""

from typing import Callable, Optional  # fcg-rewrite

from database.models import ProxyRequestLog  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


class ProxyRequestAudit:  # fcg-rewrite
    """Persist request-level proxy audit entries."""

    def __init__(self, session_factory: Callable[[], object]) -> None:  # fcg-rewrite
        self._session_factory = session_factory  # fcg-rewrite

    async def record_gateway_proxy_request(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        upstream_api_config_id: str,  # fcg-rewrite
        model_requested: str,  # fcg-rewrite
        model_used: str,  # fcg-rewrite
        provider: str,  # fcg-rewrite
        input_detection_id: Optional[str] = None,  # fcg-rewrite
        output_detection_id: Optional[str] = None,  # fcg-rewrite
        input_blocked: bool = False,  # fcg-rewrite
        output_blocked: bool = False,  # fcg-rewrite
        request_tokens: int = 0,  # fcg-rewrite
        response_tokens: int = 0,  # fcg-rewrite
        total_tokens: int = 0,  # fcg-rewrite
        status: str = "success",  # fcg-rewrite
        error_message: Optional[str] = None,  # fcg-rewrite
        response_time_ms: int = 0,  # fcg-rewrite
    ) -> None:  # fcg-rewrite
        await self._write_log(  # fcg-rewrite
            request_id=request_id,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            upstream_api_config_id=upstream_api_config_id,  # fcg-rewrite
            proxy_config_id=None,  # fcg-rewrite
            model_requested=model_requested,  # fcg-rewrite
            model_used=model_used,  # fcg-rewrite
            provider=provider,  # fcg-rewrite
            input_detection_id=input_detection_id,  # fcg-rewrite
            output_detection_id=output_detection_id,  # fcg-rewrite
            input_blocked=input_blocked,  # fcg-rewrite
            output_blocked=output_blocked,  # fcg-rewrite
            request_tokens=request_tokens,  # fcg-rewrite
            response_tokens=response_tokens,  # fcg-rewrite
            total_tokens=total_tokens,  # fcg-rewrite
            status=status,  # fcg-rewrite
            error_message=error_message,  # fcg-rewrite
            response_time_ms=response_time_ms,  # fcg-rewrite
        )

    async def record_proxy_request(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        proxy_config_id: str,  # fcg-rewrite
        model_requested: str,  # fcg-rewrite
        model_used: str,  # fcg-rewrite
        provider: str,  # fcg-rewrite
        input_detection_id: Optional[str] = None,  # fcg-rewrite
        output_detection_id: Optional[str] = None,  # fcg-rewrite
        input_blocked: bool = False,  # fcg-rewrite
        output_blocked: bool = False,  # fcg-rewrite
        request_tokens: int = 0,  # fcg-rewrite
        response_tokens: int = 0,  # fcg-rewrite
        total_tokens: int = 0,  # fcg-rewrite
        status: str = "success",  # fcg-rewrite
        error_message: Optional[str] = None,  # fcg-rewrite
        response_time_ms: int = 0,  # fcg-rewrite
    ) -> None:  # fcg-rewrite
        await self._write_log(  # fcg-rewrite
            request_id=request_id,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            proxy_config_id=proxy_config_id,  # fcg-rewrite
            model_requested=model_requested,  # fcg-rewrite
            model_used=model_used,  # fcg-rewrite
            provider=provider,  # fcg-rewrite
            input_detection_id=input_detection_id,  # fcg-rewrite
            output_detection_id=output_detection_id,  # fcg-rewrite
            input_blocked=input_blocked,  # fcg-rewrite
            output_blocked=output_blocked,  # fcg-rewrite
            request_tokens=request_tokens,  # fcg-rewrite
            response_tokens=response_tokens,  # fcg-rewrite
            total_tokens=total_tokens,  # fcg-rewrite
            status=status,  # fcg-rewrite
            error_message=error_message,  # fcg-rewrite
            response_time_ms=response_time_ms,  # fcg-rewrite
        )

    async def _write_log(self, **kwargs) -> None:  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            db.add(ProxyRequestLog(**kwargs))  # fcg-rewrite
            db.commit()  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            log_target = kwargs.get("request_id", "unknown")  # fcg-rewrite
            logger.error("Failed to log proxy request %s: %s", log_target, exc)  # fcg-rewrite
            db.rollback()  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite
