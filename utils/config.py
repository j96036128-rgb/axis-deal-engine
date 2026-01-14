"""
Configuration management.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """
    Application configuration.

    Loads from environment variables with sensible defaults.
    """

    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # Scraping
    scraper_type: str = field(default_factory=lambda: os.getenv("SCRAPER_TYPE", "mock"))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))

    # Scoring
    default_target_bmv: float = field(
        default_factory=lambda: float(os.getenv("DEFAULT_TARGET_BMV", "15.0"))
    )

    # Data
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "./data"))

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment."""
        return cls()

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "scraper_type": self.scraper_type,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "default_target_bmv": self.default_target_bmv,
            "data_dir": self.data_dir,
        }
