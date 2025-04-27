from typing import Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
import logging

logger = logging.getLogger(__name__)

class Driver:
    """A context manager class for handling Chrome WebDriver initialization and cleanup.
    
    This class provides a convenient way to create and manage a Chrome WebDriver instance
    with various configuration options. It can be used with a context manager (with statement)
    to ensure proper cleanup of resources.
    
    Attributes:
        download_dir (str): Directory where downloads will be saved
        user_dir (Optional[str]): User data directory for Chrome
        headless (bool): Whether to run Chrome in headless mode
        simulate_slow_conn (bool): Whether to simulate slow network conditions
        driver (Optional[WebDriver]): The Selenium WebDriver instance
    """
    
    def __init__(
        self,
        download_dir: str | None = None,
        user_dir: str | None = None,
        headless: bool = True,
        simulate_slow_conn: bool = False
    ):
        """Initialize the Driver with the given configuration.
        
        Args:
            download_dir: Directory where downloads will be saved
            user_dir: Optional user data directory for Chrome
            headless: Whether to run Chrome in headless mode
            simulate_slow_conn: Whether to simulate slow network conditions
        """
        self.download_dir = str(Path(download_dir).absolute()) if download_dir else None
        self.user_dir = str(Path(user_dir).absolute()) if user_dir else None
        self.headless = headless
        self.simulate_slow_conn = simulate_slow_conn
        self.driver: WebDriver | None = None
        
    def _configure_options(self) -> Options:
        """Configure and return Chrome options.
        
        Returns:
            Options: Configured Chrome options
        """
        options = Options()
        
        # Basic Chrome arguments
        chrome_args = [
            "--disable-search-engine-choice-screen",
            "--start-maximized",
            "--window-size=1920,1080",
            "--no-sandbox",
            "--no-gpu",
            "--disable-extensions",
            "--dns-prefetch-disable"
        ]
        
        # Add headless mode if requested
        if self.headless:
            chrome_args.append("--headless")
            
        # Add all arguments to options
        for arg in chrome_args:
            options.add_argument(arg)
            
        # Configure user directory if specified
        if self.user_dir:
            options.add_argument(f"user-data-dir={self.user_dir}")
            
        # Configure download preferences
        if self.download_dir:
            prefs = {
                "download.default_directory": self.download_dir,
                "download.directory_upgrade": True,
                "download.prompt_for_download": False,
            }
            options.add_experimental_option("prefs", prefs)
        
        return options
        
    def __enter__(self) -> WebDriver:
        """Initialize and return the WebDriver when entering the context.
        
        Returns:
            WebDriver: The configured Chrome WebDriver instance
            
        Raises:
            Exception: If driver initialization fails
        """
        logger.info('Starting browser...')
        
        try:
            # Initialize the driver with configured options
            options = self._configure_options()
            self.driver = webdriver.Chrome(options=options)
            
            # Configure timezone
            tz_params = {'timezoneId': 'Europe/Rome'}
            self.driver.execute_cdp_cmd('Emulation.setTimezoneOverride', tz_params)
            
            # Configure network conditions if requested
            if self.simulate_slow_conn:
                self.driver.set_network_conditions(
                    offline=False,
                    latency=5,  # additional latency (ms)
                    download_throughput=500 * 1024,  # maximal throughput
                    upload_throughput=500 * 1024  # maximal throughput
                )
            
            # Set implicit wait timeout
            self.driver.implicitly_wait(30)
            
            logger.info('Browser started successfully.')
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            self.__exit__(None, None, None)  # Cleanup in case of failure
            raise
            
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up the WebDriver when exiting the context.
        
        Args:
            exc_type: The type of the exception that occurred, if any
            exc_val: The instance of the exception that occurred, if any
            exc_tb: The traceback of the exception that occurred, if any
        """
        if self.driver:
            try:
                logger.info('Closing browser...')
                self.driver.quit()
                logger.info('Browser closed successfully.')
            except Exception as e:
                logger.warning(f"Error while closing browser: {e}")
            finally:
                self.driver = None
