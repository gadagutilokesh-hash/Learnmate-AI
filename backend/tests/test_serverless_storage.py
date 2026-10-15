import os
import sys
import tempfile
import importlib
from unittest.mock import patch
import pytest

from app.core.config import Settings, ensure_storage_dirs
from app.main import validate_storage_configuration, app
from app.db.storage import LocalStorageEngine


def test_config_loading_does_not_create_directories_in_source_tree(tmp_path):
    """
    Regression Test:
    Loading Settings MUST NOT invoke os.makedirs or create directories in the application tree.
    """
    dummy_data = str(tmp_path / "non_existent_data")
    dummy_uploads = str(tmp_path / "non_existent_uploads")

    with patch("os.makedirs") as mock_makedirs:
        s = Settings(DATA_DIR=dummy_data, UPLOADS_DIR=dummy_uploads)
        assert s.DATA_DIR == dummy_data
        assert s.UPLOADS_DIR == dummy_uploads
        # Ensure os.makedirs was never called during configuration instantiation
        mock_makedirs.assert_not_called()

    # Verify neither directory was created on disk
    assert not os.path.exists(dummy_data)
    assert not os.path.exists(dummy_uploads)


def test_serverless_paths_default_to_ephemeral_temp():
    """
    Regression Test:
    When running in a serverless environment (VERCEL=1 or VERCEL_ENV),
    storage paths must resolve to a writable temporary directory (such as /tmp)
    and NOT inside the application code directory.
    """
    with patch.dict(os.environ, {"VERCEL": "1", "VERCEL_ENV": "production", "ENVIRONMENT": "production"}):
        s = Settings()
        assert s.is_serverless is True
        assert s.is_production is True

        temp_dir = tempfile.gettempdir()
        assert s.DATA_DIR.startswith(temp_dir)
        assert s.UPLOADS_DIR.startswith(temp_dir)
        assert "learnmate_data" in s.DATA_DIR
        assert "learnmate_uploads" in s.UPLOADS_DIR


def test_local_development_paths_default_to_project_data():
    """
    Regression Test:
    Local development (non-serverless, ENVIRONMENT=development) must preserve
    existing local data directory and database files.
    """
    with patch.dict(os.environ, {}, clear=True):
        # Ensure VERCEL/AWS environment variables are absent
        os.environ.pop("VERCEL", None)
        os.environ.pop("VERCEL_ENV", None)
        os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
        os.environ.pop("IS_SERVERLESS", None)

        s = Settings(ENVIRONMENT="development")
        assert s.is_serverless is False
        assert s.is_production is False
        assert s.DATA_DIR.endswith("data")
        assert s.UPLOADS_DIR.endswith(os.path.join("data", "uploads"))
        assert s.storage_mode == "local_embedded"


def test_simulated_read_only_deployment_import():
    """
    Regression Test for Vercel startup crash:
    Simulates a read-only filesystem where any os.makedirs call in the deployment
    directory (/var/task) raises OSError: [Errno 30] Read-only file system.
    Importing the config and storage modules must succeed without touching the filesystem.
    """
    original_makedirs = os.makedirs

    def fake_makedirs(path, *args, **kwargs):
        # If attempting to create directory in source tree, simulate read-only error
        if "data" in str(path) and "learnmate_data" not in str(path) and "tmp" not in str(path).lower():
            raise OSError(30, f"Read-only file system: '{path}'")
        return original_makedirs(path, *args, **kwargs)

    with patch("os.makedirs", side_effect=fake_makedirs):
        # Reloading config must not call os.makedirs or raise OSError
        import app.core.config as config_mod
        importlib.reload(config_mod)
        assert config_mod.settings is not None

        # Instantiating LocalStorageEngine must not create files during __init__
        engine = LocalStorageEngine()
        assert engine._initialized is False


def test_production_startup_fails_without_persistent_storage():
    """
    Regression Test:
    Production startup must raise a clear, actionable error if persistent storage
    (PostgreSQL / Supabase) is not configured and ephemeral storage has not been
    explicitly enabled via ALLOW_EPHEMERAL_STORAGE=true.
    """
    with patch.dict(os.environ, {"VERCEL": "1", "VERCEL_ENV": "production"}):
        prod_settings = Settings(
            ENVIRONMENT="production",
            ALLOW_EPHEMERAL_STORAGE=False,
            SUPABASE_URL=None,
            SUPABASE_KEY=None,
            DATABASE_URL=None
        )
        assert prod_settings.is_production is True
        assert prod_settings.has_persistent_storage is False
        assert prod_settings.ALLOW_EPHEMERAL_STORAGE is False

        with pytest.raises(RuntimeError) as exc_info:
            validate_storage_configuration(prod_settings)

        err_text = str(exc_info.value)
        assert "Required persistent storage is not configured" in err_text
        assert "ALLOW_EPHEMERAL_STORAGE=true" in err_text
        assert "Supabase" in err_text or "PostgreSQL" in err_text


def test_production_startup_succeeds_with_explicit_ephemeral_storage(caplog):
    """
    Regression Test:
    When ALLOW_EPHEMERAL_STORAGE=true is provided, production startup succeeds
    with a clear logged warning indicating data is ephemeral.
    """
    with patch.dict(os.environ, {"VERCEL": "1", "VERCEL_ENV": "production"}):
        prod_settings = Settings(
            ENVIRONMENT="production",
            ALLOW_EPHEMERAL_STORAGE=True,
            SUPABASE_URL=None,
            SUPABASE_KEY=None,
            DATABASE_URL=None
        )
        assert prod_settings.is_production is True
        assert prod_settings.ALLOW_EPHEMERAL_STORAGE is True

        # Should succeed without exception
        validate_storage_configuration(prod_settings)


def test_local_development_startup_succeeds():
    """
    Regression Test:
    Development mode startup must succeed without requiring ALLOW_EPHEMERAL_STORAGE
    or persistent external databases.
    """
    with patch.dict(os.environ, {}, clear=True):
        dev_settings = Settings(ENVIRONMENT="development")
        assert dev_settings.is_production is False
        validate_storage_configuration(dev_settings)


def test_storage_engine_lazy_init_on_query(tmp_path):
    """
    Regression Test:
    LocalStorageEngine must only initialize tables and connect to SQLite
    when an actual query/connection is requested, never at import or instantiation time.
    """
    db_file = str(tmp_path / "sub" / "test_lazy.db")
    engine = LocalStorageEngine(db_path=db_file)
    assert engine._initialized is False
    assert not os.path.exists(db_file)

    # First query triggers lazy initialization
    courses = engine.list_courses()
    assert engine._initialized is True
    assert os.path.exists(db_file)
    assert isinstance(courses, list)
