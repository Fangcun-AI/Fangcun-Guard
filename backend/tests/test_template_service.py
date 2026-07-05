import services.template_service as templates


class Query:
    def __init__(self, db):
        self.db = db

    def filter_by(self, **_values):
        return self

    def count(self):
        return self.db.existing

    def filter(self, *_conditions):
        return self

    def all(self):
        return self.db.defaults

    def first(self):
        return self.db.results.pop(0)


class Db:
    def __init__(self, *, existing=0, defaults=None, results=None):
        self.existing = existing
        self.defaults = defaults or []
        self.results = results or []
        self.added = []
        self.commits = 0

    def query(self, _model):
        return Query(self)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("rollback should not run")


def test_create_defaults_skips_existing_tenant_templates():
    db = Db(existing=3)
    assert templates.create_user_default_templates(db, "tenant") == 3
    assert not db.added


def test_user_template_falls_back_to_system_default():
    fallback = object()
    assert templates.get_user_template(Db(results=[None, fallback]), "tenant", "S1", "low") is fallback


def test_default_template_prefers_tenant_value():
    own = object()
    assert templates.get_default_template(Db(results=[own]), "tenant") is own
