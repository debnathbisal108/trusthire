"""
Shared pytest configuration.
All fixtures are defined in tests/test_api.py for co-location,
but any truly global fixtures live here.
"""
import os
import sys

# Make sure the api package is importable from the tests directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables before any app imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trusthire:test_password@localhost:5432/trusthire_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NEXTAUTH_SECRET", "ci-test-secret-placeholder-32-chars-ok!")
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LLM_MODEL", "llama3.2:8b")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin123")
os.environ.setdefault("MINIO_BUCKET", "trusthire-test")
os.environ.setdefault("ENCRYPTION_KEY", "")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("EMAIL_PROVIDER", "smtp")
os.environ.setdefault("FROM_EMAIL", "test@test.com")
