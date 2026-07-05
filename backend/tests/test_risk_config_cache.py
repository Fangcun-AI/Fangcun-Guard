import asyncio

from services.risk_config_cache import RiskConfigCache


class StubRiskConfigCache(RiskConfigCache):
    def __init__(self):
        super().__init__(cache_ttl=60)
        self.risk_loads = 0
        self.sensitivity_loads = 0
        self.trigger_loads = 0

    async def _load_from_db(self, cache_key: str, use_application_id: bool = True):
        self.risk_loads += 1
        return {"S1": False, "S2": True}

    async def _load_sensitivity_thresholds_from_db(
        self, cache_key: str, use_application_id: bool = True
    ):
        self.sensitivity_loads += 1
        return {"low": 0.1, "medium": 0.2, "high": 0.3}

    async def _load_trigger_level_from_db(
        self, cache_key: str, use_application_id: bool = True
    ):
        self.trigger_loads += 1
        return "high"


class FailingRiskConfigCache(RiskConfigCache):
    async def _load_from_db(self, cache_key: str, use_application_id: bool = True):
        raise RuntimeError("database unavailable")


def test_risk_config_cache_reuses_values_and_returns_copies():
    async def exercise():
        cache = StubRiskConfigCache()
        first = await cache.get_user_risk_config(application_id="app-a")
        first["S1"] = True
        second = await cache.get_user_risk_config(application_id="app-a")

        assert second == {"S1": False, "S2": True}
        assert cache.risk_loads == 1

        await cache.invalidate_user_cache(application_id="app-a")
        await cache.get_user_risk_config(application_id="app-a")
        assert cache.risk_loads == 2

    asyncio.run(exercise())


def test_sensitivity_invalidation_removes_both_cached_values():
    async def exercise():
        cache = StubRiskConfigCache()
        assert await cache.get_sensitivity_thresholds(application_id="app-a") == {
            "low": 0.1,
            "medium": 0.2,
            "high": 0.3,
        }
        assert await cache.get_sensitivity_trigger_level(application_id="app-a") == "high"

        await cache.invalidate_sensitivity_cache(application_id="app-a")
        await cache.get_sensitivity_thresholds(application_id="app-a")
        await cache.get_sensitivity_trigger_level(application_id="app-a")

        assert cache.sensitivity_loads == 2
        assert cache.trigger_loads == 2

    asyncio.run(exercise())


def test_database_failure_uses_enabled_defaults():
    async def exercise():
        cache = FailingRiskConfigCache()
        config = await cache.get_user_risk_config(application_id="app-a")

        assert len(config) == 21
        assert set(config.values()) == {True}

    asyncio.run(exercise())
