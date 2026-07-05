import asyncio
from types import SimpleNamespace

import services.ban_policy_service as bans


class Result:
    def __init__(self, row=None, rows=None, rowcount=0):
        self.row = row
        self.rows = rows or []
        self.rowcount = rowcount

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Db:
    def __init__(self, *results):
        self.results = list(results)
        self.closed = False
        self.commits = 0

    def execute(self, *_args):
        return self.results.pop(0)

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("rollback should not run")

    def close(self):
        self.closed = True


def test_risk_level_accepts_existing_chinese_aliases():
    assert bans._risk_level("高风险") == "high_risk"
    assert bans._risk_level("medium_risk") == "medium_risk"


def test_check_ip_banned_is_explicit_noop_without_schema():
    assert asyncio.run(bans.BanPolicyManager.check_ip_banned("tenant", "127.0.0.1")) is None


def test_get_policy_serializes_identifiers_and_closes_session():
    db = Db(Result(("policy", "tenant", "application", True, "high_risk", 3, 10, 60, None, None)))
    bans.get_admin_db_session = lambda: db
    policy = asyncio.run(bans.BanPolicyManager.get_ban_policy("application"))
    assert policy["id"] == "policy"
    assert policy["application_id"] == "application"
    assert db.closed


def test_unban_commits_and_reports_changed_row():
    db = Db(Result(rowcount=1))
    bans.get_admin_db_session = lambda: db
    assert asyncio.run(bans.BanPolicyManager.unban_user("application", "user"))
    assert db.commits == 1
    assert db.closed
