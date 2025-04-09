# plant_protection_report/config.py
import os
import yaml # Import YAML library
from dotenv import load_dotenv
from pathlib import Path
import platform
import logging
from tempfile import TemporaryDirectory

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = Path(".config/config.yaml")
CREDENTIALS_ENV_FILE = "credentials.env"

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


def _resolve_path(base_path, config_path_str):
    """Resolves a path relative to the base path (project root)."""
    path = Path(config_path_str)
    if not path.is_absolute():
        return (base_path / path).resolve()
    return path.resolve()

def load_configuration():
    """Loads configuration from YAML file and environment variables."""
    logger.info(f"Loading configuration from: {CONFIG_FILE_PATH}")

    # --- Load .env file first ---
    if Path(CREDENTIALS_ENV_FILE).exists():
        load_dotenv(CREDENTIALS_ENV_FILE)
        logger.debug(f"Loaded environment variables from {CREDENTIALS_ENV_FILE}")

    # --- Load YAML configuration file ---
    if not CONFIG_FILE_PATH.is_file():
        raise ConfigError(f"Configuration file not found: {CONFIG_FILE_PATH}")

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
        if not isinstance(yaml_config, dict):
             raise ConfigError(f"Invalid YAML format in {CONFIG_FILE_PATH}. Root should be a dictionary.")
    except yaml.YAMLError as e:
        raise ConfigError(f"Error parsing YAML file {CONFIG_FILE_PATH}: {e}")
    except IOError as e:
        raise ConfigError(f"Error reading configuration file {CONFIG_FILE_PATH}: {e}")

    # --- Prepare the final config dictionary ---
    config = {}
    project_root = Path(__file__).parent.parent # Assumes config.py is one level down from root

    # --- Helper function to get nested keys safely ---
    def get_nested(data, keys, default=None):
        value = data
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    # --- General Settings ---
    config['year'] = yaml_config['general']['year']

    if not isinstance(config.get('year'), int):
         raise ConfigError("Invalid 'general.year' in config.yaml: must be an integer.")

    # --- Path Settings (resolve relative paths) ---
    paths_config = get_nested(yaml_config, ['paths'], {})
    config['download_dir'] = str(_resolve_path(project_root, paths_config.get('download_dir', TemporaryDirectory().name)))
    config['user_dir'] = str(_resolve_path(project_root, paths_config.get('user_dir', 'user_dir')))
    config['static_data_path'] = _resolve_path(project_root, paths_config.get('static_data_dir', 'data'))
    config['template_path'] = _resolve_path(project_root, paths_config.get('template_dir', 'templates'))
    config['google_creds_path'] = str(_resolve_path(project_root, paths_config.get('google_creds_file', 'gcloud_key.json')))

    # Adjust user_dir path for Windows if it's relative 
    if platform.system() == 'Windows' and not Path(config["user_dir"]).is_absolute():
        config["user_dir"] = str(Path.cwd() / config["user_dir"])

    # Create download directory if it doesn't exist
    Path(config["download_dir"]).mkdir(exist_ok=True, parents=True)
    logger.debug(f"Download directory set to: {config['download_dir']}")
    logger.debug(f"User directory set to: {config['user_dir']}")

    # --- Threshold Settings ---
    thresholds_config = get_nested(yaml_config, ['thresholds'], {})
    config['default_mm'] = get_nested(thresholds_config, ['default_mm'], 30)
    config['default_days'] = get_nested(thresholds_config, ['default_days'], 14)
    config['t1_factor'] = get_nested(thresholds_config, ['t1_factor'], 0.75)

    # Validate threshold types
    if not isinstance(config['default_mm'], (int, float)): raise ConfigError("'thresholds.default_mm' must be a number.")
    if not isinstance(config['default_days'], int): raise ConfigError("'thresholds.default_days' must be an integer.")
    if not isinstance(config['t1_factor'], (int, float)): raise ConfigError("'thresholds.t1_factor' must be a number.")

    # --- Driver Settings ---
    config['run_headless'] = yaml_config['driver'].get('headless', True)
    config['simulate_slow_connection'] = yaml_config['driver'].get('slow_conn', False)

    if not isinstance(config['run_headless'], bool): raise ConfigError("'smartfarmer.headless' must be true or false.")


    # --- SmartFarmer Settings & Credentials ---
    sm_config = get_nested(yaml_config, ['smartfarmer'], {})
    sm_user_env = get_nested(sm_config, ['username_env'], 'SM_USERNAME')
    sm_pwd_env = get_nested(sm_config, ['password_env'], 'SM_PASSWORD')
    config['sm_user'] = os.getenv(sm_user_env)
    config['sm_pwd'] = os.getenv(sm_pwd_env)


    # --- SBR Settings & Credentials ---
    sbr_config = get_nested(yaml_config, ['sbr'], {})
    config['sbr_station_id'] = str(get_nested(sbr_config, ['station_id'], '103')) # Ensure string
    sbr_user_env = get_nested(sbr_config, ['username_env'], 'SBR_USERNAME')
    sbr_pwd_env = get_nested(sbr_config, ['password_env'], 'SBR_PASSWORD')
    config['sbr_user'] = os.getenv(sbr_user_env)
    config['sbr_pwd'] = os.getenv(sbr_pwd_env)


    # --- Gmail Settings & Credentials ---
    gmail_config = get_nested(yaml_config, ['gmail'], {})
    config['email_recipients'] = get_nested(gmail_config, ['recipients'], [])
    gm_user_env = get_nested(gmail_config, ['username_env'], 'GM_USERNAME')
    gm_pwd_env = get_nested(gmail_config, ['password_env'], 'GM_APPKEY')
    config['gm_user'] = os.getenv(gm_user_env)
    config['gm_pwd'] = os.getenv(gm_pwd_env)

    if not isinstance(config['email_recipients'], list):
         raise ConfigError("'gmail.recipients' must be a list of email addresses.")


    # --- Validate Essential Credentials ---
    required_credentials = {
        'sm_user': sm_user_env,
        'sm_pwd': sm_pwd_env,
        'sbr_user': sbr_user_env,
        'sbr_pwd': sbr_pwd_env,
        'gm_user': gm_user_env,
        'gm_pwd': gm_pwd_env,
    }
    missing_creds = [env_var for key, env_var in required_credentials.items() if not config[key]]
    if missing_creds:
        raise ConfigError(f"Missing required credentials. Please set these environment variables (defined in {CREDENTIALS_ENV_FILE} or system environment): {', '.join(missing_creds)}")


    # --- Optional Google Sheets Settings ---
    # config['google_sheets_config'] = get_nested(yaml_config, ['google_sheets'])


    logger.info(f"Configuration loaded successfully for Year={config['year']}")
    logger.debug(f"Full config (excluding passwords): { {k: v for k, v in config.items() if 'pwd' not in k} }")

    return config