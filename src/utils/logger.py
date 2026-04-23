"""
Project Astra - Logger Configuration
Structured logging with Loguru for milestone tracking and DOM debugging.
"""

import sys
from pathlib import Path
from loguru import logger

from src.constants import DEFAULT_STATE


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def configure_logger() -> None:
    """Configure loguru with file rotation and structured levels."""
    logger.remove()

    # Console handler: INFO and above
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File handler: DEBUG and above with rotation
    logger.add(
        LOG_DIR / "astra.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        enqueue=True,
    )

    # Error file handler: ERROR and above
    logger.add(
        LOG_DIR / "astra_errors.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="5 MB",
        retention="30 days",
        enqueue=True,
    )

    logger.info("Loguru configured for Project Astra")


# Export configured logger instance
configure_logger()
