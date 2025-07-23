import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from ash_utils.healthcheck.utils import HealthCheckContextManager


def test_context_manager_creates_readiness_file(temp_files):
    """Test that context manager creates readiness file on enter."""
    heartbeat_file, readiness_file = temp_files

    with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
        assert readiness_file.exists()
        assert not heartbeat_file.exists()  # Only created when update_func is called
        assert callable(update_func)


def test_context_manager_cleans_up_files_on_exit(temp_files):
    """Test that context manager removes files on exit."""
    heartbeat_file, readiness_file = temp_files

    with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
        update_func()  # Create heartbeat file
        assert readiness_file.exists()
        assert heartbeat_file.exists()

    # After context exit, both files should be removed
    assert not readiness_file.exists()
    assert not heartbeat_file.exists()


def test_update_heartbeat_file_creates_file(temp_files):
    """Test that update_heartbeat_file creates the heartbeat file."""
    heartbeat_file, readiness_file = temp_files

    with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
        assert not heartbeat_file.exists()
        update_func()
        assert heartbeat_file.exists()
        assert update_func.__name__ == "update_heartbeat_file"


def test_update_heartbeat_file_updates_timestamp(temp_files):
    """Test that update_heartbeat_file updates the file timestamp."""
    heartbeat_file, readiness_file = temp_files

    with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
        update_func()
        first_mtime = heartbeat_file.stat().st_mtime

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        update_func()
        second_mtime = heartbeat_file.stat().st_mtime

        assert second_mtime > first_mtime


@patch("ash_utils.healthcheck.utils.logger")
def test_context_manager_handles_readiness_file_creation_error(mock_logger, temp_files):
    """Test that context manager handles readiness file creation errors gracefully."""
    heartbeat_file, readiness_file = temp_files

    # Make the readiness file directory read-only to cause permission error
    readiness_file.parent.chmod(0o444)

    try:
        with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
            # Should still work even if readiness file creation fails
            update_func()
            assert heartbeat_file.exists()
    except Exception:
        pass
    finally:
        # Restore permissions
        readiness_file.parent.chmod(0o755)

    # Verify that logger.error was called for readiness file creation error
    mock_logger.error.assert_called()
    error_calls = [call for call in mock_logger.error.call_args_list if "Could not create readiness file" in str(call)]
    assert len(error_calls) >= 1


@patch("ash_utils.healthcheck.utils.logger")
def test_context_manager_handles_heartbeat_file_update_error(mock_logger, temp_files):
    """Test that context manager handles heartbeat file update errors gracefully."""
    heartbeat_file, readiness_file = temp_files

    with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
        # Make the heartbeat file directory read-only to cause permission error
        heartbeat_file.parent.chmod(0o444)

        try:
            update_func()  # Should not raise exception, just log error
            assert not heartbeat_file.exists()
        except Exception:
            pass
        finally:
            # Restore permissions
            heartbeat_file.parent.chmod(0o755)

    # Verify that logger.error was called for heartbeat file update error
    mock_logger.error.assert_called()
    error_calls = [call for call in mock_logger.error.call_args_list if "Could not update heartbeat file" in str(call)]
    assert len(error_calls) >= 1


@pytest.mark.parametrize(
    "file_to_remove,expected_remaining_file",
    [
        ("readiness_file", "heartbeat_file"),
        ("heartbeat_file", "readiness_file"),
    ],
)
def test_context_manager_cleanup_with_missing_files(temp_files, file_to_remove, expected_remaining_file):
    """Test that context manager cleanup works when files are missing."""
    heartbeat_file, readiness_file = temp_files

    with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
        update_func()  # Create heartbeat file
        # Remove the specified file manually
        if file_to_remove == "readiness_file":
            readiness_file.unlink()
        else:
            heartbeat_file.unlink()

    # Cleanup should work fine even if one file is missing
    # The remaining file should still be cleaned up
    if expected_remaining_file == "heartbeat_file":
        assert not heartbeat_file.exists()
    else:
        assert not readiness_file.exists()


def test_context_manager_exception_handling(temp_files):
    """Test that context manager properly cleans up even when exceptions occur."""
    heartbeat_file, readiness_file = temp_files

    try:
        with HealthCheckContextManager(heartbeat_file, readiness_file) as update_func:
            update_func()
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Files should still be cleaned up even after exception
    assert not readiness_file.exists()
    assert not heartbeat_file.exists()
