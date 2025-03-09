from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def init_driver(download_dir, user_dir = None, headless = True, simulate_slow_conn = False, timeout = 0):
    
    logger.info('Starte browser...')
    # Specify driver options
    options = Options()
    options.add_argument("--disable-search-engine-choice-screen")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")

    if headless:
        options.add_argument('--headless')

    options.add_argument('--no-sandbox')
    options.add_argument('--no-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--dns-prefetch-disable')

    ## Set the download directory and user_data_dir
    if user_dir:
        options.add_argument(f"user-data-dir={user_dir}")
    prefs = {
        "download.default_directory": download_dir,
        "download.directory_upgrade": True,
        "download.prompt_for_download": False,
    }
    options.add_experimental_option("prefs", prefs)

    ## Open Browser
    driver = webdriver.Chrome(options=options)

    # Set timezone
    tz_params = {'timezoneId': 'Europe/Rome'}
    driver.execute_cdp_cmd('Emulation.setTimezoneOverride', tz_params)

    ## Simulate slow internet connection (for debugging)
    if simulate_slow_conn:
        driver.set_network_conditions(
            offline=False,
            latency=5,  # additional latency (ms)
            download_throughput=500 * 1024,  # maximal throughput
            upload_throughput=500 * 1024)  # maximal throughput

    driver.implicitly_wait(timeout)
    logger.info('Browser gestartet.')
    return(driver)
