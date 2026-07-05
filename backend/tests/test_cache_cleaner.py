import services.cache_cleaner as cleaner


def test_clean_once_expires_auth_entries_and_reads_stats():
    calls = []
    cleaner.auth_cache = type("Auth", (), {"clear_expired": lambda self: calls.append("clear"), "size": lambda self: 0})()
    cleaner.rate_limiter = type("Limiter", (), {"_local_cache": {}})()
    cleaner.keyword_cache = type("Keywords", (), {"get_cache_info": lambda self: {"blacklist_keywords": 0, "whitelist_keywords": 0}})()
    cleaner.CacheJanitor()._clean_once()
    assert calls == ["clear"]
