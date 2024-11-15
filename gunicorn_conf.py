import argparse
import os
import sys

from dotenv import load_dotenv

# Check if we're in a Docker/ECS environment
# In container environments, APP_ENV is typically set in the container config
app_env = os.environ.get("APP_ENV")

# If APP_ENV is set, we're likely in a containerized environment
# In this case, we should prioritize environment variables already set in the container
if not app_env:
    # Only attempt to load .env files for local development
    # Check if --env is provided in command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env",
        type=str,
        choices=["dev", "docker", "prod", "local", "rc"],
        default="local",
        help="Specify the environment to use (dev, prod, local, docker default=local).",
    )

    try:
        # Parse only known args to avoid conflicts with gunicorn's own arguments
        args, _ = parser.parse_known_args()
        env = args.env

        # Load the appropriate environment file
        env_file = f".{env}.env"
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
        elif os.path.exists(".env"):
            load_dotenv(".env", override=True)
    except:
        # If argument parsing fails, try to load default .env
        if os.path.exists(".env"):
            load_dotenv(".env", override=True)

workers = os.getenv("WORKERS_COUNT", 2)
threads = os.getenv("WORKERS_PER_CORE", 2)
reload = os.getenv("RELOAD", True)

PORT = os.getenv("PORT", 8800)

bind = f"0.0.0.0:{PORT}"
worker_class = "uvicorn.workers.UvicornWorker"

timeout = 240  # Worker timeout in seconds
keepalive = 5  # Keep-alive timeout for client connections

accesslog = "-"  # '-' means log to stdout
errorlog = "-"  # '-' means log to stderr
loglevel = "info"

preload_app = False  # Preload application to reduce worker start-up time
