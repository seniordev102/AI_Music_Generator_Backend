import argparse
import os

import uvicorn
from dotenv import load_dotenv

from app.config import settings
from app.logger.logger import logger


def load_environment(env: str) -> None:
    # Check if we're in a Docker/ECS environment
    if env == "local":
        env_file = ".env"
    else:
        env_file = f".{env}.env"

    if os.path.exists(env_file):
        logger.debug(f"Loading environment variables from {env_file}")
        # Set override=True to ensure values from the specified env file take precedence
        load_dotenv(env_file, override=True)
    elif os.path.exists(".env"):
        logger.debug(f"Environment file {env_file} not found, falling back to .env")
        load_dotenv(".env", override=True)
    else:
        logger.debug("No environment files found. Using system environment variables.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start FastAPI server with environment options."
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["dev", "docker", "prod", "local", "rc"],
        default="local",
        help="Specify the environment to use (dev, prod, local, docker default=local).",
    )
    args = parser.parse_args()

    # Load environment variables based on the selected environment
    load_environment(args.env)

    # Start the server
    logger.debug(f"Starting server... {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "app.app:get_app",
        workers=settings.WORKERS_COUNT,
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.RELOAD,
        factory=True,
    )


if __name__ == "__main__":
    main()
