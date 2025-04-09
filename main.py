import logging
import logging.config
import sys
import datetime
from pytz import timezone
from webhandler.SBR_requests import SBR

# Load custom exceptions and config loader first
# ConfigError is now defined in config.py
from src.config import load_configuration, FetchError, ProcessingError, ReportError, ConfigError

from src.utils.web_driver import init_driver, close_driver
from src.clients.smartfarmer_client import SmartFarmerClient
#from src.clients.sbr_client import SBRClient
from src.data_loaders.static_data import StaticDataLoader
from src.processing.data_processor import DataProcessor
from src.reporting.reporter import Reporter
import pandas as pd

# --- Setup Logging ---
##TODO: Move logging configuration to .yaml file and use dict-config
logging.config.fileConfig(".config/logging.conf", disable_existing_loggers=False)
logger = logging.getLogger() # Get root logger
logger.info("Successfully loaded logging configuration from .config/logging.conf")

# Suppress noisy logs from libraries (apply AFTER fileConfig)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("webdriver_manager").setLevel(logging.WARNING)
logging.getLogger("WDM").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING) # If using sheets


# --- Main Execution Logic ---
def run_report_generation():
    """Main function to orchestrate the report generation process."""
    config = None
    driver = None
    reporter_instance = None # To allow sending failure emails
    exit_code = 0 # Assume success initially

    try:
        logger.info("--- Starting Pflanzenschutz Report Generation ---")
        ##TODO: Simplify load_configuration function by removing get_nested calls?
        config = load_configuration()

        # --- Initialize Components ---
        logger.info("Initializing components...")
        static_loader = StaticDataLoader(config['static_data_path'], config['t1_factor'])
        ##TODO: Transform init_driver in a class with __enter__and __exit__ methods to use as context manager. Can also be imported from webhandler
        try:
            driver = init_driver(
                download_dir=config['download_dir'],
                user_dir=config['user_dir'],
                headless=config['run_headless']
            )
        except Exception as e:
            logger.critical(f"Failed to initialize WebDriver: {e}", exc_info=True)
            raise FetchError(f"WebDriver initialization failed: {e}") from e # Raise specific error

        sm_client = SmartFarmerClient(driver, config['sm_user'], config['sm_pwd'], config['download_dir'])
        processor = DataProcessor(config, None) # Static data loaded later
        reporter_instance = Reporter(config) # Initialize reporter
        logger.info("Components initialized.")

        # --- Fetch Data ---
        logger.info("--- Fetching Data ---")
        smartfarmer_data = sm_client.fetch_report_data(config['year'])

        sbr_data = None
        if not smartfarmer_data.empty and 'Datum' in smartfarmer_data.columns:
            try:
                sm_dates = pd.to_datetime(smartfarmer_data['Datum'], format="%d/%m/%Y", errors='coerce').dropna()
                if not sm_dates.empty:
                    min_date = sm_dates.min()
                    # Ensure min_date is not NaT
                    if pd.notna(min_date):
                        max_date = datetime.datetime.now(tz = timezone('Europe/Rome'))
                        # Check if min_date has timezone, add if necessary (assuming Europe/Rome based on SBRClient)
                        if min_date.tzinfo is None:
                            min_date = min_date.tz_localize('Europe/Rome')
                        logger.info(f"Fetching SBR data from {min_date.strftime('%Y-%m-%d')} to now.")
                        with SBR(config['sbr_user'], config['sbr_pwd']) as client:
                            sbr_data = client.get_stationdata(
                                station_id="103",
                                start=min_date,
                                end=max_date,
                                type='meteo'
                            )
                    else:
                        logger.warning("Minimum date from SmartFarmer data is invalid (NaT). Skipping SBR fetch.")
                else:
                    logger.warning("No valid dates found in SmartFarmer data after conversion. Cannot determine SBR range.")
            except FetchError as e:
                logger.warning(f"Failed to fetch SBR data: {e}. Proceeding without rainfall data.")
            except Exception as e:
                logger.warning(f"Unexpected error preparing for SBR fetch: {e}. Proceeding without rainfall data.", exc_info=True)
        else:
            logger.warning("SmartFarmer data is empty or missing 'Datum' column. Skipping SBR fetch.")

        logger.info("--- Data Fetching Complete ---")

        # --- Process Data ---
        logger.info("--- Processing Data ---")
        processor.static_data = static_loader.load_all()
        processed_data = processor.process(smartfarmer_data, sbr_data)
        logger.info("--- Data Processing Complete ---")

        # --- Generate and Send Report ---
        logger.info("--- Generating and Sending Report ---")
        html_report = reporter_instance.generate_html_report(processed_data)
        reporter_instance.send_email(html_report)

        # Optional: Send to Google Sheets
        # gs_config = config.get('google_sheets_config')
        # if gs_config and not processed_data.empty:
        #     try:
        #         reporter_instance.send_to_google_sheets(
        #             processed_data,
        #             gs_config.get('spreadsheet_name', 'DefaultSpreadsheet'),
        #             gs_config.get('worksheet_name', 'DefaultWorksheet')
        #         )
        #     except ReportError as e:
        #          logger.warning(f"Could not send data to Google Sheets: {e}")

        logger.info("--- Reporting Complete ---")

    # --- Error Handling ---
    except (ConfigError, FetchError, ProcessingError, ReportError) as e:
        logger.critical(f"Report generation failed: {e}", exc_info=True)
        # Send failure notification email if possible
        try:
            if config and reporter_instance: # Check if config/reporter were initialized
                subject = f"FEHLER: Pflanzenschutz Report Generation Failed - {datetime.date.today().strftime('%Y-%m-%d')}"
                body = f"<h1>Report Generation Failed</h1><p><strong>Error Type:</strong> {type(e).__name__}</p><p><strong>Message:</strong> {e}</p><p>Check application logs for details.</p>"
                # Use a simplified send method or reuse reporter's method carefully
                # Creating a simple message here:
                from email.message import EmailMessage
                import smtplib

                msg = EmailMessage()
                msg["Subject"] = subject
                msg['From'] = config.get('gm_user', 'error@example.com')
                msg['To'] = ", ".join(config.get('email_recipients', []))
                msg.set_content("Report generation failed. Please check logs. Enable HTML for details.")
                msg.add_alternative(body, subtype="html")

                if config.get('gm_user') and config.get('gm_pwd') and config.get('email_recipients'):
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
                        smtp_server.login(config['gm_user'], config['gm_pwd'])
                        smtp_server.send_message(msg)
                    logger.info("Sent failure notification email.")
                else:
                    logger.warning("Could not send failure email: Gmail config incomplete.")

        except Exception as mail_err:
            logger.error(f"Failed to send failure notification email: {mail_err}", exc_info=True)
            exit_code = 1 # Indicate failure
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        exit_code = 1 # Indicate failure

    # --- Cleanup ---
    finally:
        logger.info("--- Cleaning up resources ---")
        if driver:
            close_driver(driver)
        # Cleanup temp dir logic might need adjustment if using default from YAML
        # The TemporaryDirectory() object needs to be stored if created in config loading
        # For simplicity now, assume download_dir is managed manually or is persistent

        logger.info(f"--- Report Generation Finished with exit code {exit_code} ---")
        sys.exit(exit_code) # Exit with appropriate code


# --- Script Entry Point ---
if __name__ == "__main__":
    # No command line args needed here anymore unless you add specific overrides
    run_report_generation()