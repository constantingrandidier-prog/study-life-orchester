"""Application configuration settings."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env file from project root if it exists
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    app_name: str = "Study-Life Orchestrator"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    # Default daily operational window
    default_day_start_hour: int = 7   # 07:00
    default_day_end_hour: int = 23    # 23:00

    # Optional AnkiWeb credentials loaded from environment variables
    ankiweb_token: str = os.getenv("ANKIWEB_TOKEN", "")
    ankiweb_email: str = os.getenv("ANKIWEB_EMAIL", "")
    ankiweb_password: str = os.getenv("ANKIWEB_PASSWORD", "")


settings = Settings()
