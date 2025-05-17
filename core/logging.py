import logging.config
import sys


def configure_logging():
    """Configure application-wide logging."""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
            },
            "file": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.FileHandler",
                "filename": "app.log",
                "mode": "a",
            },
        },
        "loggers": {
            "": {  # root logger
                "handlers": ["default", "file"],
                "level": "INFO",
                "propagate": True,
            }
        },
    }

    logging.config.dictConfig(config)


# Configure logging when module is imported
configure_logging()
