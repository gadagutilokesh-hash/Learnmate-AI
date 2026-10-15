import os
import sys
import subprocess
import tempfile
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.core.config import Settings, ensure_storage_dirs, is_path_in_source_tree
from app.db.storage import LocalStorageEngine
from app.main import validate_storage_configuration, app


def test_import_app_without_opening_database_prematurely():
    """
    Regression Test 1:
    Importing the app and storage module must NOT connect to SQLite prematurely
    before FastAPI lifespan has executed.
    """
    # 1. Verify that instantiating LocalStorageEngine does NOT call sqlite3.connect
    with patch("sqlite3.connect") as mock_connect:
        engine = LocalStorageEngine(db_path="/dummy/path/learnmate.db")
        assert engine._initialized is False
        mock_connect.assert_not_called()

    # 2. In a clean subprocess, verify that importing app.main does not invoke sqlite3.connect
    code = (
        "import sys, sqlite3\n"
        "def blocked_connect(*args, **kwargs):\n"
        "    raise AssertionError('sqlite3.connect was called during module import!')\n"
        "sqlite3.connect = blocked_connect\n"
        "import app.main\n"
        "print('IMPORT_SUCCESS')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Import crashed with: {result.stderr}"
    assert "IMPORT_SUCCESS" in result.stdout


def test_database_initialization_in_valid_writable_directory(tmp_path):
    """
    Regression Test 2:
    Database initialization in a valid writable directory creates the parent
    directory, creates the SQLite file, applies schema migrations, and sets
    engine._initialized to True.
    """
    target_dir = tmp_path / "valid_render_dir" / "subdir"
    target_db = str(target_dir / "learnmate.db")
    assert not target_dir.exists()

    engine = LocalStorageEngine(db_path=target_db)
    assert engine._initialized is False

    # Trigger initialization via explicit _init_db() or query
    engine._init_db()
    assert target_dir.exists()
    assert os.path.exists(target_db)
    assert engine._initialized is True

    # Check that schema tables were created
    with sqlite3.connect(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        assert "courses" in tables
        assert "documents" in tables
        assert "document_chunks" in tables
        assert "users" in tables


def test_unwritable_or_invalid_path_fails_with_clear_diagnostic(tmp_path):
    """
    Regression Test 3:
    Clear failure messages for an unwritable or invalid path.
    Must report the actual configured path in an actionable RuntimeError,
    and must NOT silently switch to /tmp.
    """
    # Case A: os.makedirs failure (e.g. Permission Denied)
    unwritable_path = str(tmp_path / "forbidden_mount" / "learnmate.db")
    with patch("os.makedirs", side_effect=OSError(13, "Permission denied")):
        engine = LocalStorageEngine(db_path=unwritable_path)
        with pytest.raises(RuntimeError) as exc_info:
            engine._init_db()

        err_msg = str(exc_info.value)
        assert "Failed to create database directory" in err_msg
        assert unwritable_path in err_msg
        assert "Render persistent disk" in err_msg
        # Must NOT have silently switched to /tmp
        assert engine.db_path == unwritable_path

    # Case B: Write probe failure (e.g. Read-only filesystem)
    readonly_dir = tmp_path / "readonly_mount"
    readonly_dir.mkdir(parents=True, exist_ok=True)
    readonly_db = str(readonly_dir / "learnmate.db")

    with patch("builtins.open", side_effect=OSError(30, "Read-only file system")):
        engine_ro = LocalStorageEngine(db_path=readonly_db)
        with pytest.raises(RuntimeError) as exc_info:
            engine_ro._init_db()

        err_msg = str(exc_info.value)
        assert "is not writable" in err_msg
        assert readonly_db in err_msg
        # Must NOT have silently switched to /tmp
        assert engine_ro.db_path == readonly_db


def test_existing_databases_remain_intact(tmp_path):
    """
    Regression Test 4:
    Existing databases remain intact.
    No automatic sample database copy over existing database, and no
    resetting, overwriting, or deleting of existing user records.
    """
    db_file = str(tmp_path / "existing_user.db")
    engine1 = LocalStorageEngine(db_path=db_file)
    created_course = engine1.create_course("Preserved Course Title", "Important User Data")
    course_id = created_course["id"]

    created_user = engine1.create_user(
        email="learner@example.com",
        password_hash="hashed_secret_pw",
        full_name="Persistent Learner"
    )
    user_id = created_user["id"]

    # Re-initialize engine pointing to the exact same existing database file
    engine2 = LocalStorageEngine(db_path=db_file)
    engine2._init_db()

    # Verify existing course and user records are completely preserved
    fetched_course = engine2.get_course(course_id)
    assert fetched_course is not None
    assert fetched_course["title"] == "Preserved Course Title"

    fetched_user = engine2.get_user_by_email("learner@example.com")
    assert fetched_user is not None
    assert fetched_user["id"] == user_id
    assert fetched_user["full_name"] == "Persistent Learner"


def test_fastapi_lifespan_initializes_storage_correctly(tmp_path):
    """
    Regression Test 5:
    FastAPI lifespan initializes storage correctly before serving requests.
    """
    disk_mount = str(tmp_path / "lifespan_disk")
    uploads_mount = str(tmp_path / "lifespan_disk" / "uploads")
    os.makedirs(disk_mount, exist_ok=True)
    os.makedirs(uploads_mount, exist_ok=True)
    test_db = os.path.join(disk_mount, "learnmate.db")

    from app.core.config import settings as app_settings
    from app.db.storage import storage as global_storage

    with patch.object(app_settings, "DATA_DIR", disk_mount), \
         patch.object(app_settings, "UPLOADS_DIR", uploads_mount), \
         patch.object(app_settings, "ENVIRONMENT", "production"), \
         patch.object(global_storage, "_custom_db_path", test_db), \
         patch.object(global_storage, "_initialized", False):

        assert global_storage._initialized is False
        assert not os.path.exists(test_db)

        # TestClient enters lifespan context manager
        with TestClient(app) as client:
            # Lifespan must have run _init_db()
            assert global_storage._initialized is True
            assert os.path.exists(test_db)

            # Health check request succeeds
            res = client.get("/api/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"


def test_render_production_without_persistent_disk_warns_and_starts(tmp_path):
    """
    Regression Test:
    When running in Render production without a persistent disk,
    validate_storage_configuration logs an explicit warning explaining data
    will not survive redeployments, but DOES NOT crash startup.
    """
    local_data = str(tmp_path / "local_data")
    s = Settings(ENVIRONMENT="production", DATA_DIR=local_data)
    with patch("logging.Logger.warning") as mock_warn:
        # validate_storage_configuration should NOT raise
        validate_storage_configuration(cfg=s)
        # Verify a warning was emitted explaining data will not survive
        assert any(
            "RENDER / CONTAINER PERSISTENCE NOTICE" in str(call_args)
            for call_args in mock_warn.call_args_list
        )


def test_render_persistent_disk_detected():
    """
    Regression Test:
    When running in Render environment (RENDER=true) with persistent disk mounted,
    DATA_DIR resolves outside the source tree and persistent disk is confirmed.
    """
    disk_mount = "/var/data"

    with patch.dict(os.environ, {"RENDER": "true", "ENVIRONMENT": "production"}):
        with patch("os.path.isdir", side_effect=lambda p: p == "/var/data"):
            # When DATA_DIR is explicitly provided or auto-detected
            s = Settings(DATA_DIR=disk_mount)
            assert s.is_render is True
            assert s.is_production is True
            assert s.DATA_DIR == os.path.abspath(disk_mount)
            assert s.has_persistent_disk is True
            assert s.has_persistent_storage is True
            assert s.storage_mode == "local_embedded"

            # Auto-detection when DATA_DIR is not set
            s_auto = Settings(DATA_DIR=None)
            assert s_auto.DATA_DIR == "/var/data"
            assert s_auto.has_persistent_disk is True
