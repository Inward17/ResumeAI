"""
Issue #26: every app module that imports db directly must get the mock database
in tests. conftest finds them by scanning the source; this checks the result.
"""
import importlib

from tests.conftest import DB_TARGETS


def test_modules_found_by_the_scan():
    # Missing from the hand-kept list before #26
    assert "app.services.jd_matching_service.db" in DB_TARGETS
    assert "app.database.db" in DB_TARGETS
    # Imports db inside functions, so it reads the patched app.database.db at call time
    assert "app.routes.unified_verification_routes.db" not in DB_TARGETS
    assert len(DB_TARGETS) == len(set(DB_TARGETS))


def test_every_db_import_is_patched(mock_db):
    for target in DB_TARGETS:
        module = importlib.import_module(target.rsplit(".", 1)[0])
        assert module.db is mock_db, target
