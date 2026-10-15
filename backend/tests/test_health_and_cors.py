import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import Settings

client = TestClient(app)

def test_api_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "active_provider" in data
    assert "provider_configured" in data
    assert "storage_mode" in data

def test_root_health_alias():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "active_provider" in data

def test_cors_preflight_production_frontend():
    origin = "https://learnmate-ai-peach.vercel.app"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type"
    }
    response = client.options("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin

def test_cors_preflight_vercel_preview():
    origin = "https://learnmate-ai-git-fix-branch.vercel.app"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type"
    }
    response = client.options("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin

def test_settings_cors_origins_parsing():
    # String format parsing from env var
    s = Settings(
        CORS_ORIGINS="https://learnmate-ai-peach.vercel.app,http://localhost:3000",
        ALLOW_EPHEMERAL_STORAGE=True
    )
    assert "https://learnmate-ai-peach.vercel.app" in s.CORS_ORIGINS
    assert "http://localhost:3000" in s.CORS_ORIGINS

    # Default settings includes the Vercel frontend origin
    default_s = Settings(ALLOW_EPHEMERAL_STORAGE=True)
    assert "https://learnmate-ai-peach.vercel.app" in default_s.CORS_ORIGINS
