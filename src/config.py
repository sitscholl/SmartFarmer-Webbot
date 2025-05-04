# plant_protection_report/config.py
import os
import yaml # Import YAML library
from dotenv import load_dotenv
from pathlib import Path
import platform
import logging
from tempfile import TemporaryDirectory

logger = logging.getLogger(__name__)

# Define custom exceptions (keep these as they are useful)
class SpintError(Exception):
    """Base exception for the application."""
    pass

class ConfigError(SpintError):
    """Error related to configuration loading or validation."""
    pass

class FetchError(SpintError):
    """Error during data fetching."""
    pass

class ProcessingError(SpintError):
    """Error during data processing."""
    pass

class ReportError(SpintError):
    """Error during report generation or sending."""
    pass


def load_configuration(config_file_path):
    """Loads configuration from YAML file and environment variables."""
    logger.info(f"Loading configuration from: {config_file_path}")

    # --- Load YAML configuration file ---
    if not Path(config_file_path).is_file():
        raise ConfigError(f"Configuration file not found: {config_file_path}")

    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        raise ConfigError(f"Error reading configuration file {config_file_path}: {e}")

    if not isinstance(config['general'].get('year'), int):
         raise ConfigError("Invalid 'general.year' in config.yaml: must be an integer.")

    # Adjust user_dir path for Windows if it's relative 
    if platform.system() == 'Windows' and not Path(config['paths']["user_dir"]).is_absolute():
        config['paths']["user_dir"] = str(Path.cwd() / config['paths']["user_dir"])

    # Create download directory if it doesn't exist
    Path(config['paths']["download_dir"]).mkdir(exist_ok=True, parents=True)
    logger.debug(f"Download directory set to: {config['paths']['download_dir']}")
    logger.debug(f"User directory set to: {config['paths']['user_dir']}")

    # --- Validate thresholds ---
    if not isinstance(config["thresholds"]['default_mm'], (int, float)):
        raise ConfigError("'thresholds.default_mm' must be a number.")
    if not isinstance(config["thresholds"]['default_days'], int):
        raise ConfigError("'thresholds.default_days' must be an integer.")
    if not isinstance(config["thresholds"]['t1_factor'], (int, float)):
        raise ConfigError("'thresholds.t1_factor' must be a number.")

    if not isinstance(config['driver']['headless'], bool):
        raise ConfigError("'driver.headless' must be true or false.")

    # --- Load .env file ---
    credentials_env_file = config['general']['env_file']
    if Path(credentials_env_file).exists():
        load_dotenv(credentials_env_file)
        logger.debug(f"Loaded environment variables from {credentials_env_file}")

    # --- SmartFarmer Settings & Credentials ---
    config['smartfarmer']['user'] = os.getenv(config['smartfarmer']['username_env'])
    config['smartfarmer']['pwd'] = os.getenv(config['smartfarmer']['password_env'])

    # --- SBR Settings & Credentials ---
    config['sbr']['user'] = os.getenv(config['sbr']['username_env'])
    config['sbr']['pwd'] = os.getenv(config['sbr']['password_env'])

    # --- Gmail Settings & Credentials ---
    config['gmail']['user'] = os.getenv(config['gmail']['username_env'])
    config['gmail']['pwd'] = os.getenv(config['gmail']['password_env'])

    if not isinstance(config['gmail']['recipients'], list):
         raise ConfigError("'gmail.recipients' must be a list of email addresses.")

    return config