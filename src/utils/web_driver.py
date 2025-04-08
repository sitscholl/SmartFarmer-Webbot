# spint/utils/web_driver.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager # Use webdriver-manager
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def init_driver(download_dir, user_dir=None, headless=True, simulate_slow_conn=False):
    """Initializes and returns a Selenium Chrome WebDriver instance."""
    logger.info('Initializing browser...')

    options = Options()
    options.add_argument("--disable-search-engine-choice-screen")
    options.add_argument("--start-maximized")
    # options.add_argument("--window-size=1920,1080") # Often redundant with start-maximized
    options.add_argument('--no-sandbox') # Often needed in containerized environments
    options.add_argument('--disable-dev-shm-usage') # Overcomes limited resource problems
    options.add_argument('--disable-extensions')
    options.add_argument('--dns-prefetch-disable')
    options.add_argument('--log-level=3') # Reduce console noise from Chrome
    options.add_experimental_option('excludeSwitches', ['enable-logging']) # Reduce console noise

    if headless:
        logger.info("Running in headless mode.")
        options.add_argument('--headless=new') # Use the new headless mode
        options.add_argument('--disable-gpu') # Generally recommended for headless
    else:
        logger.info("Running in non-headless mode.")

    # Set download directory and user profile
    prefs = {
        "download.default_directory": str(download_dir), # Ensure string path
        "download.directory_upgrade": True,
        "download.prompt_for_download": False,
        "profile.default_content_settings.popups": 0, # Disable popups if possible
        "safebrowsing.enabled": True # Keep safety features
    }
    options.add_experimental_option("prefs", prefs)

    if user_dir:
        logger.info(f"Using user data directory: {user_dir}")
        options.add_argument(f"user-data-dir={user_dir}")
    else:
         logger.info("Using default user data directory.")

    try:
        logger.info("Setting up ChromeDriver using webdriver-manager...")
        # Use webdriver-manager to handle driver download/updates
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver initialized successfully.")

        # Set timezone
        tz_params = {'timezoneId': 'Europe/Rome'}
        driver.execute_cdp_cmd('Emulation.setTimezoneOverride', tz_params)
        logger.debug("Timezone set to Europe/Rome.")

        # Simulate slow connection if needed (for debugging)
        if simulate_slow_conn:
            logger.warning("Simulating slow network connection.")
            driver.set_network_conditions(
                offline=False,
                latency=500,  # increased latency (ms)
                download_throughput=500 * 1024,  # 500 kbps
                upload_throughput=500 * 1024)

        # Set a default implicit wait (can be overridden temporarily)
        driver.implicitly_wait(10) # Reduced default wait, rely more on explicit waits
        logger.debug("Default implicit wait set to 10s.")

        return driver

    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {e}", exc_info=True)
        raise # Re-raise the exception after logging

def close_driver(driver):
    """Safely quits the WebDriver instance."""
    if driver:
        try:
            logger.info("Closing WebDriver...")
            driver.quit()
            logger.info("WebDriver closed successfully.")
        except Exception as e:
            logger.error(f"Error closing WebDriver: {e}", exc_info=True)