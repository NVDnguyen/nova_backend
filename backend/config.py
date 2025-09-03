# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import EmailStr
from datetime import timedelta
from typing import Literal

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Pydantic's BaseSettings provides type validation and a single source of truth.
    """
    # --- Application Configuration ---
    APP_ENV: Literal["development", "production"] = "development"

    # --- Database & Cache ---
    MONGO_URI: str = "mongodb://mongo:27017/shopping_cart_db"
    REDIS_URI: str = "redis://redis:6379/0"

    # --- Security ---
    JWT_SECRET_KEY: str = "super-secret-key-for-dev"
    VIETQR_WEBHOOK_SECRET_KEY: str = "your_vietqr_webhook_secret_key"

    # --- Initial Admin User ---
    ADMIN_EMAIL: EmailStr = "admin@example.com"

    # --- VietQR Configuration ---
    VIETQR_BANK_BIN: str = "970436"
    VIETQR_ACCOUNT_NO: str = "1234567890"
    VIETQR_ACCOUNT_NAME: str = "NGUYEN VAN A"

    # --- JWT Token Expiration (not from .env, but good to keep here) ---
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(days=30)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False, # Environment variables are often uppercase
    )

# Create a single, importable instance of the settings
settings = Settings()