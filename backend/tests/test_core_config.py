from app.core.config import Settings


def test_settings_initialization():
    """
    Tests that Settings loads default values correctly and normalizes Supabase DB URIs properly.
    """
    custom_settings = Settings(
        PROJECT_NAME="OpsMind Test Engine",
        ENVIRONMENT="testing",
        SUPABASE_URL="https://testproject.supabase.co",
        SUPABASE_ANON_KEY="anon-key-123",
        SUPABASE_JWT_SECRET="jwt-secret-456",
        DATABASE_URL="postgresql://postgres:testpass@db.testproject.supabase.co:5432/postgres",
    )

    assert custom_settings.PROJECT_NAME == "OpsMind Test Engine"
    assert custom_settings.ENVIRONMENT == "testing"
    assert custom_settings.SUPABASE_URL == "https://testproject.supabase.co"
    assert "postgresql+asyncpg://" in custom_settings.SQLALCHEMY_DATABASE_URI


def test_cors_origins_parsing():
    """
    Tests CORS origins list string parsing.
    """
    custom_settings = Settings(
        BACKEND_CORS_ORIGINS="https://app.opsmind.io, https://admin.opsmind.io"
    )
    assert len(custom_settings.BACKEND_CORS_ORIGINS) == 2
    assert "https://app.opsmind.io" in custom_settings.BACKEND_CORS_ORIGINS
    assert "https://admin.opsmind.io" in custom_settings.BACKEND_CORS_ORIGINS
