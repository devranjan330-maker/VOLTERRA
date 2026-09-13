import sys
import os
from loguru import logger

# Retrieve log level from environment (default INFO)
log_level = os.getenv("LOGURU_LEVEL", "INFO").upper()

# Configure logger format: JSON for structured logging
logger.remove()
logger.add(
    sink=sys.stderr,
    level=log_level,
    format="{\"time\": \"{time:ISO8601}\", \"level\": \"{level}\", \"message\": \"{message}\", \"module\": \"{module}\", \"function\": \"{function}\", \"line\": {line}}",
    serialize=True,
)

# Export a singleton logger instance
log = logger
