# spint/utils/helpers.py
import time
import datetime
from pathlib import Path
from pytz import timezone
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Keep wait_for_download, wait_for_page_stability, temporary_implicit_wait
# Modify wait_for_download to raise an error instead of sys.exit

def wait_for_download(download_dir, expected_filename=None, extension=None, timeout=60, stability_interval=3):
    """
    Waits for a file download to complete in the specified directory.
    Raises FetchError if the download times out or fails.
    """
    from ..config import FetchError # Import locally to avoid circular dependency if helpers used elsewhere

    if not expected_filename and not extension:
        raise ValueError("Either expected_filename or extension must be provided.")

    download_dir = Path(download_dir)
    start_time = datetime.datetime.now(tz=timezone('Europe/Berlin'))
    pattern = expected_filename if expected_filename else f'*{extension}'
    logger.info(f"Waiting for download matching '{pattern}' in {download_dir} (timeout: {timeout}s)")

    last_checked_size = {} # Store last known size to detect stability

    while (datetime.datetime.now(tz=timezone('Europe/Berlin')) - start_time).total_seconds() < timeout:
        files = list(download_dir.glob(pattern))
        # Filter out typical temporary files used during download.
        files = [f for f in files if not f.name.endswith(('.crdownload', '.part', '.tmp')) and f.is_file()]
        logger.debug(f"Found potential files: {files}")

        if files:
            # Sort files by modification time (most recent first) as creation time can be unreliable
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            candidate = files[0] # Check the most recently modified file first
            logger.debug(f"Checking candidate file: {candidate}")

            try:
                current_size = candidate.stat().st_size
                last_size = last_checked_size.get(candidate)

                if last_size is not None and current_size == last_size and current_size > 0:
                     # File exists, size hasn't changed since last check, and it's not empty
                    logger.info(f"Download complete: {candidate} (size: {current_size} bytes)")
                    return candidate
                elif last_size is not None and current_size != last_size:
                    logger.debug(f"File size changed ({last_size}b -> {current_size}b), waiting...")
                    last_checked_size[candidate] = current_size
                elif last_size is None:
                     logger.debug(f"First check for {candidate}, size {current_size}b. Checking stability...")
                     last_checked_size[candidate] = current_size

            except FileNotFoundError:
                logger.debug(f"Candidate file {candidate} disappeared.")
                if candidate in last_checked_size:
                    del last_checked_size[candidate] # Remove stale entry
                continue # Re-scan directory

        else:
            # Reset sizes if no matching files are found
             last_checked_size = {}

        time.sleep(stability_interval) # Wait before next check

    # Timeout occurred
    logger.error(f"Download timed out after {timeout} seconds. No stable file found matching '{pattern}'.")
    raise FetchError(f"Download timed out for pattern '{pattern}' in {download_dir}")


def wait_for_page_stability(driver, check_interval=1, timeout=30):
    """
    Wait until the page's HTML stabilizes (i.e., doesn't change)
    for at least one check interval. Returns False on timeout.
    """
    start = time.time()
    last_source = ""
    # Initial fetch might need a small delay
    time.sleep(0.5)
    try:
        last_source = driver.execute_script("return document.documentElement.outerHTML")
    except Exception as e:
        logger.warning(f"Error getting initial page source: {e}")
        return False # Cannot determine stability

    logger.debug("Checking for page stability...")
    while time.time() - start < timeout:
        time.sleep(check_interval)
        try:
            current_source = driver.execute_script("return document.documentElement.outerHTML")
            if current_source == last_source:
                logger.debug("Page source stabilized.")
                return True
            last_source = current_source
            logger.debug("Page source changed, waiting...")
        except Exception as e:
            logger.warning(f"Error getting current page source: {e}. Assuming instability.")
            # Optionally reset last_source or just continue waiting
            last_source = "" # Force re-check next iteration

    logger.warning(f"Page did not stabilize within {timeout} seconds.")
    return False

def validate_date(date_str, target_format="%d.%m.%Y"):
    """Validates if a string matches the target date format."""
    try:
        datetime.datetime.strptime(date_str, target_format)
        return True
    except ValueError:
        # Raise specific error for clarity
        raise ValueError(f'Date "{date_str}" needs to be in {target_format} format.')

@contextmanager
def temporary_implicit_wait(driver, wait_time, original_wait=30):
    """Temporarily changes Selenium's implicit wait time."""
    driver.implicitly_wait(wait_time)
    logger.debug(f"Implicit wait set to {wait_time}s temporarily.")
    try:
        yield
    finally:
        driver.implicitly_wait(original_wait)
        logger.debug(f"Implicit wait restored to {original_wait}s.")