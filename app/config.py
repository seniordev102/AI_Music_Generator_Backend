import argparse
import os
import sys

from pydantic import BaseSettings


# Check if --env is provided in command line arguments
def get_env_file():
    # Check if we're in a Docker/ECS environment
    # In container environments, APP_ENV is typically set in the container config
    app_env = os.environ.get("APP_ENV")

    # If APP_ENV is set, we're likely in a containerized environment
    # In this case, we should prioritize environment variables already set in the container
    if app_env:
        return None  # Let Pydantic use environment variables directly

    # For local development, use command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env",
        type=str,
        choices=["dev", "docker", "prod", "local", "rc"],
        default="local",
        help="Specify the environment to use (dev, prod, local, docker default=local).",
    )

    # Parse only known args to avoid conflicts with other arguments
    try:
        args, _ = parser.parse_known_args()
        env = args.env

        # Construct the environment file name
        env_file = f".{env}.env"

        # Check if the environment file exists
        if os.path.exists(env_file):
            return env_file
    except:
        # If argument parsing fails, fall back to default
        pass

    # Fall back to default .env if specified environment file doesn't exist
    return ".env" if os.path.exists(".env") else None


class Settings(BaseSettings):
    APP_NAME: str
    WORKERS_COUNT: int = 1
    HOST: str = "localhost"
    PORT: int = 8900
    RELOAD: bool = True
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_NAME: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    API_PREFIX: str
    DB_ECHO: bool = False
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_DEFAULT_REGION: str
    AWS_S3_BUCKET_NAME: str
    THUMBNAIL_WIDTH: int = 500
    THUMBNAIL_HEIGHT: int = 500
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int
    EMAIL_TOKEN_SALT: str
    EMAIL_EXPIRE_SECONDS: int = 600
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLIC_KEY: str
    STRIPE_API_VERSION: str
    STRIPE_WEBHOOK_SECRET: str
    OPENAI_API_KEY: str
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_EMAIL: str
    APP_ENV: str
    ACTIVE_CAMPAIGN_API_URL: str
    ACTIVE_CAMPAIGN_API_KEY: str
    ELEVEN_LAB_API_KEY: str
    STRIPE_ENCRYPTION_KEY: str
    MUSIC_GENERATOR_API_URL: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_HOST: str
    MUSIC_GENERATOR_API_KEY: str
    CRON_API_KEY: str = "your-secure-api-key"  # API key for cron job endpoints

    @property
    def DB_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    @property
    def DB_SYNC_URL(self) -> str:
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    class Config:
        env_file = get_env_file()


settings = Settings()
