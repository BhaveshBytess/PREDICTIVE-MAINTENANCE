"""
Application Configuration — Pydantic Settings

Centralized configuration management using environment variables.
Loads from .env file automatically with sensible defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Priority: Environment variables > .env file > defaults
    """
    
    # === API Configuration ===
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Predictive Maintenance"
    
    # === CORS Configuration ===
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8080",
    ]
    
    # === InfluxDB Configuration ===
    INFLUX_URL: str = "http://localhost:8086"
    INFLUX_TOKEN: str = ""
    INFLUX_ORG: str = ""
    INFLUX_BUCKET: str = "sensor_data"
    
    # === Environment ===
    ENVIRONMENT: str = "local"  # local, development, staging, production
    
    # === Settings Configuration ===
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),  # Check both paths
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Singleton instance
settings = Settings()
