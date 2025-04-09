# spint/clients/smartfarmer_client.py
import logging
import time
import pandas as pd
from xlsx2csv import Xlsx2csv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..utils.helpers import wait_for_page_stability, wait_for_download, temporary_implicit_wait
from ..config import FetchError # Use custom exception

logger = logging.getLogger(__name__)

class SmartFarmerClient:
    """Client for interacting with the SmartFarmer website."""

    BASE_URL = 'https://app.smartfarmer.it/#/auth/welcome/'

    def __init__(self, driver, username, password, download_dir):
        self.driver = driver
        self.username = username
        self.password = password
        self.download_dir = download_dir

    def _login(self):
        """Logs into SmartFarmer if necessary."""
        logger.info('Checking SmartFarmer login status...')
        self.driver.get(self.BASE_URL)

        if not wait_for_page_stability(self.driver, check_interval=1, timeout=30):
             raise FetchError("SmartFarmer landing page did not stabilize.")

        try:
            # Look for email input field as indicator for login needed
            email_input = self.driver.find_element(By.XPATH, '//input[@type="email"]')
            logger.info("Login required.")

            if not self.username or not self.password:
                raise FetchError("SmartFarmer login required but username or password not provided.")

            email_input.send_keys(self.username)
            self.driver.find_element(By.XPATH, '//button[normalize-space()="weiter ►"]').click()

            # Wait for password field
            password_input = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.XPATH, '//input[@type="password"]'))
            )
            password_input.send_keys(self.password)
            self.driver.find_element(By.XPATH, '//button[normalize-space()="login"]').click()

            # Wait for login confirmation or dashboard element
            WebDriverWait(self.driver, 30).until(
                 EC.any_of( # Wait for either a popup button or main menu element
                    EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="später"]')),
                    EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="jetzt nicht"]')),
                    EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Berichte"]')),
                )
            )
            logger.info('SmartFarmer login successful.')

        except (NoSuchElementException, TimeoutException):
            # Assume already logged in if email field not found or login process times out differently
            # Check for a known element on the dashboard to be sure
             try:
                 WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="Berichte"]'))
                 )
                 logger.info('SmartFarmer already logged in.')
             except TimeoutException:
                 logger.error("Could not confirm login status or find dashboard element.")
                 # Consider saving screenshot for debugging
                 # self.driver.save_screenshot("smartfarmer_login_error.png")
                 raise FetchError("Failed to log in or verify login status on SmartFarmer.")

    def _close_popups(self):
        """Closes known pop-up dialogs."""
        popups = [
            ('//button[normalize-space()="später"]', "App aktualisiert popup"),
            ('//button[normalize-space()="jetzt nicht"]', "SmartFarmer installieren popup"),
        ]
        for xpath, description in popups:
            try:
                # Use a short wait to avoid delays if popups aren't present
                with temporary_implicit_wait(self.driver, 1):
                    button = self.driver.find_element(By.XPATH, xpath)
                    if button.is_displayed():
                        button.click()
                        logger.debug(f"Closed '{description}'.")
                        time.sleep(0.5) # Short pause after click
            except NoSuchElementException:
                logger.debug(f"'{description}' not found.")
            except Exception as e:
                logger.warning(f"Error closing popup '{description}': {e}")


    def _navigate_to_report(self, year):
        """Navigates to the measures report list for the specified year."""
        logger.info(f'Navigating to measures report for year {year}...')
        try:
            # Use explicit waits for navigation robustness
            WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Berichte"]'))
            ).click()
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[normalize-space()="Maßnahmen"]'))
            ).click()
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[normalize-space()="Liste"]'))
            ).click()
            logger.debug("Navigated to report list.")

            # Select the desired year using 'Kalenderjahr'
            logger.debug(f'Filtering for year {year}')

            # Click dropdown first (Erntejahr or Kalenderjahr)
            year_dropdown = WebDriverWait(self.driver, 20).until(EC.any_of(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Erntejahr")]')),
                EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Kalenderjahr")]'))
            ))
            year_dropdown.click()
            logger.debug("Clicked year type dropdown.")

            # Click the specific calendar year
            year_xpath = f'//span[normalize-space()="Kalenderjahr {year}"]'
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, year_xpath))
            ).click()
            logger.info(f"Selected 'Kalenderjahr {year}'.")

            # Wait for table/data to potentially reload
            if not wait_for_page_stability(self.driver, check_interval=2, timeout=45):
                # This might be okay if data loads async, but log a warning
                logger.warning("SmartFarmer report page might not have fully stabilized after year selection.")
            else:
                logger.debug("Report page stabilized after year selection.")

        except TimeoutException as e:
            logger.error(f"Timeout during navigation or year selection: {e}", exc_info=True)
            # self.driver.save_screenshot("smartfarmer_nav_error.png")
            raise FetchError("Failed to navigate to the SmartFarmer report page.")
        except Exception as e:
            logger.error(f"Unexpected error during navigation: {e}", exc_info=True)
            # self.driver.save_screenshot("smartfarmer_nav_unexpected_error.png")
            raise FetchError(f"Unexpected error navigating SmartFarmer: {e}")


    def _download_report(self, year):
        """Triggers the report download and waits for completion."""
        logger.info('Attempting to download the report...')
        try:
            # Check if there are entries before attempting download
            # Use a short wait to allow the "No entries" message to appear if applicable
            time.sleep(2) # Give page time to render message
            if "Keine passenden Einträge gefunden" in self.driver.page_source:
                msg = f'SmartFarmer: No entries found for year {year}.'
                logger.warning(msg)
                # Decide if this should be an error or just return empty data
                # Raising an error seems appropriate as no report can be generated
                raise FetchError(msg)

            # Locate and click the download button
            # Using a more robust XPath if possible, the full one is fragile
            # Try finding based on title or icon if available, otherwise stick to the provided one
            dbutton_xpath = '/html/body/div[1]/div/div[1]/div[1]/div[1]/div/div[2]/div/div[2]/div/div/div[1]/span[2]/span/button[2]' # Fragile XPath
            # Alternative (example): '//button[@title="Exportieren"]' or similar if title exists
            try:
                 download_button = WebDriverWait(self.driver, 15).until(
                     EC.element_to_be_clickable((By.XPATH, dbutton_xpath))
                 )
                 download_button.click()
                 logger.debug("Clicked download button.")
            except TimeoutException:
                 logger.error("Could not find or click the download button.")
                 # self.driver.save_screenshot("smartfarmer_download_button_error.png")
                 raise FetchError("SmartFarmer download button not found or clickable.")


            # Wait for the download to complete
            downloaded_file = wait_for_download(self.download_dir, extension='.xlsx', timeout=90)
            logger.info(f'SmartFarmer data downloaded successfully: {downloaded_file}')
            return downloaded_file

        except FetchError as e:
            # Re-raise FetchErrors directly (like "No entries found")
            raise e
        except Exception as e:
            logger.error(f"Error during download process: {e}", exc_info=True)
            # self.driver.save_screenshot("smartfarmer_download_error.png")
            raise FetchError(f"Failed to download SmartFarmer report: {e}")

    def _open_xlsx(self, file):
        csv_name = str(file).replace('.xlsx', '.csv')
        Xlsx2csv(file, outputencoding="latin-1").convert(csv_name)
        return pd.read_csv(csv_name, encoding = 'latin-1')

    def fetch_report_data(self, year):
        """Logs in, navigates, downloads the report, and reads it into a DataFrame."""
        try:
            self._login()
            self._close_popups()
            self._navigate_to_report(year)
            downloaded_file_path = self._download_report(year)

            logger.info(f"Reading downloaded Excel file: {downloaded_file_path}")
            # Use pandas to read the excel file directly
            df = self._open_xlsx(downloaded_file_path)
            logger.info(f"Successfully read SmartFarmer data. Shape: {df.shape}")

            # Optional: Delete the downloaded file after reading
            try:
                downloaded_file_path.unlink()
                logger.debug(f"Deleted temporary file: {downloaded_file_path}")
            except OSError as e:
                logger.warning(f"Could not delete temporary file {downloaded_file_path}: {e}")

            return df

        except (FetchError, Exception) as e:
            logger.error(f"Failed to fetch SmartFarmer report for year {year}: {e}", exc_info=True)
            # Re-raise as FetchError for consistent handling upstream
            raise FetchError(f"SmartFarmer fetch failed: {e}") from e