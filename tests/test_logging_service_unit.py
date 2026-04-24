from app.logs.services.logging_service import log_to_db
from unittest.mock import patch


def test_log_to_db_marks_session_to_skip_refdata_cache_invalidation():
    class DummySession:
        def __init__(self):
            self.info = {}
            self.added = None
            self.skip_flag_seen_at_commit = None

        def add(self, obj):
            self.added = obj

        def commit(self):
            self.skip_flag_seen_at_commit = self.info.get("_skip_refdata_cache_invalidation")

        def rollback(self):
            return None

        def close(self):
            return None

    session = DummySession()

    class DummyLog:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    with patch("app.logs.services.logging_service._make_independent_session", return_value=session), patch(
        "app.logs.services.logging_service.Log",
        new=DummyLog,
    ), patch(
        "app.logs.services.logging_service.has_app_context",
        return_value=False,
    ):
        log_to_db(user="tester", action="unit-test")

    assert session.added is not None
    assert session.skip_flag_seen_at_commit is True
