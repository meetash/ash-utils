import datetime
import typing as t
from pathlib import Path
from types import TracebackType

from loguru import logger


class HealthCheckContextManager:
    """Context manager for health check file management and signal handling."""

    def __init__(self, heartbeat_file: Path, readiness_file: Path) -> None:
        self.heartbeat_file = heartbeat_file
        self.readiness_file = readiness_file

    def __enter__(self) -> t.Callable:
        """Set up health check files. Return update_heartbeat_file function."""
        self.create_readiness_file()
        return self.update_heartbeat_file

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Clean up health check files and restore original signal handlers."""
        self.cleanup_health_files()

    def update_heartbeat_file(self) -> None:
        """Updates the heartbeat file timestamp."""
        try:
            self.heartbeat_file.touch()
            logger.debug(f"Heartbeat file updated at {datetime.datetime.now(tz=datetime.UTC)}")
        except Exception as e:
            logger.error(f"Could not update heartbeat file {self.heartbeat_file}: {e}")

    def create_readiness_file(self) -> None:
        """Creates the readiness file."""
        try:
            self.readiness_file.touch()
            logger.debug(f"Readiness file created at {datetime.datetime.now(tz=datetime.UTC)}")
        except Exception as e:
            logger.error(f"Could not create readiness file {self.readiness_file}: {e}")

    def cleanup_health_files(self) -> None:
        """Removes the health check files."""
        for f in (self.heartbeat_file, self.readiness_file):
            f.unlink(missing_ok=True)
            logger.debug(f"Cleaned up {f}")
