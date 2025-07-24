'''
Logging configuration for the application.
This module sets up logging to both a file and the console using Loguru.
'''
import sys
from pathlib import Path
from loguru import logger

LOG_DIR = "logs"
LOG_PATH = f"{LOG_DIR}/app.log"

# Ensure log directory exists
Path(LOG_DIR).mkdir(exist_ok=True)

# Remove any default handlers
logger.remove()

# File handler (10MB max, keep 5 backups)
logger.add(
    LOG_PATH,
    rotation="10 MB",
    retention=5,
    level="DEBUG",
    format=
    "{time:YYYY-MM-DD HH:mm:ss,SSS} {level: <8} [{file}:{line}] {message}",
)

# Console handler (INFO+)
logger.add(
    sys.stdout,
    level="INFO",
    format=
    "{time:YYYY-MM-DD HH:mm:ss,SSS} {level: <8} [{file}:{line}] {message}",
)
