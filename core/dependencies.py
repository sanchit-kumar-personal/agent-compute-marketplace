from core.settings import Settings

# Settings singleton
_settings = None


def get_settings() -> Settings:
    """Dependency that provides application settings."""
    assert (
        _settings is not None
    ), "Settings not initialized. Make sure startup() was called."
    return _settings


def init_settings():
    """Initialize settings singleton."""
    global _settings
    _settings = Settings()


def clear_settings():
    """Clear settings singleton."""
    global _settings
    _settings = None
