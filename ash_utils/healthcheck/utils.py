import datetime
import signal
import sys
import tempfile
from pathlib import Path

from loguru import logger

HEARTBEAT_FILE = Path(tempfile.gettempdir(), "heartbeat")
READINESS_FILE = Path(tempfile.gettempdir(), "ready")


def update_heartbeat_file():
    """Updates the heartbeat file timestamp."""
    try:
        HEARTBEAT_FILE.touch()
    except Exception as e:
        logger.error(f"ERROR: Could not update heartbeat file {HEARTBEAT_FILE}: {e}")


def create_readiness_file():
    """Creates the readiness file."""
    try:
        READINESS_FILE.touch()
        logger.debug(f"Readiness file created at {datetime.datetime.now()}")
    except Exception as e:
        logger.error(f"ERROR: Could not create readiness file {READINESS_FILE}: {e}")


def register_signals():
    def _signal_handler(signum, frame):
        """Signal Handler for Graceful Shutdown"""
        logger.debug(f"Received signal {signum}. Shutting down gracefully...")
        cleanup_health_files()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)  # For local testing with Ctrl+C


def cleanup_health_files():
    """Removes the health check files."""
    for f in (HEARTBEAT_FILE, READINESS_FILE):
        try:
            f.unlink(missing_ok=True)
            logger.debug(f"Cleaned up {f}")
        except Exception as e:
            logger.error(f"Error cleaning up {f}: {e}")
