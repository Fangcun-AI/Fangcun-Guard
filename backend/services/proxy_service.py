"""Facade for proxy persistence, transport, and audit collaborators."""

from database.connection import get_admin_db_session
from services.proxy_config_store import ProxyConfigStore
from services.proxy_credentials import ProxyCredentialCipher
from services.proxy_request_audit import ProxyRequestAudit
from services.proxy_transport import ProxyTransport

class ProxyService:
    def __init__(self):
        self._credentials = ProxyCredentialCipher()
        self._configs = ProxyConfigStore(get_admin_db_session, self._credentials)
        self._transport = ProxyTransport(self._credentials)
        self._audit = ProxyRequestAudit(get_admin_db_session)

    async def close(self):
        await self._transport.close()

    async def list_tenant_models(self, tenant_id: str):
        return await self._configs.list_tenant_models(tenant_id)

    async def load_upstream_api_config(self, upstream_api_id: str, tenant_id: str):
        return await self._configs.load_upstream_api_config(upstream_api_id, tenant_id)

    async def load_tenant_model_config(self, tenant_id: str, model_name: str):
        return await self._configs.load_tenant_model_config(tenant_id, model_name)

    async def create_user_model(self, tenant_id: str, model_data):
        return await self._configs.create_user_model(tenant_id, model_data)

    async def update_user_model(self, tenant_id: str, model_id: str, model_data):
        return await self._configs.update_user_model(tenant_id, model_id, model_data)

    async def delete_user_model(self, tenant_id: str, model_id: str):
        return await self._configs.delete_user_model(tenant_id, model_id)

    async def relay_streaming_chat_completion(self, model_config, request_data, request_id: str):
        async for chunk in self._transport.relay_streaming_chat_completion(model_config, request_data, request_id):
            yield chunk

    async def relay_chat_completion(self, model_config, request_data, request_id: str, messages=None):
        return await self._transport.relay_chat_completion(model_config, request_data, request_id, messages=messages)

    async def relay_completion(self, model_config, request_data, request_id: str):
        return await self._transport.relay_completion(model_config, request_data, request_id)

    async def dispatch_upstream_gateway(self, api_config, model_name: str, messages, **kwargs):
        return await self._transport.dispatch_upstream_gateway(api_config, model_name, messages, **kwargs)

    async def record_gateway_proxy_request(self, **kwargs):
        return await self._audit.record_gateway_proxy_request(**kwargs)

    async def record_proxy_request(self, **kwargs):
        return await self._audit.record_proxy_request(**kwargs)

# Create global instance
proxy_service = ProxyService()
