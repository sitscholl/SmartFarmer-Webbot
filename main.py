import logging
import logging.config
import sys
import datetime
from pytz import timezone
import pandas as pd
from webhandler.SBR_requests import SBR

from src.config import load_configuration
from src.utils.web_driver import init_driver, close_driver
from src.clients.smartfarmer_client import SmartFarmerClient
from src.data_loaders.static_data import StaticDataLoader
from src.processing.data_processor import DataProcessor
from src.config import load_configuration

from src.driver import Driver
from src.clients.smartfarmer_client import SmartFarmerClient

# --- Main Execution Logic ---
def run_report_generation():
    """Main function to orchestrate the report generation process."""
    config = None
    reporter_instance = None

    try:
        
        config = load_configuration('.config/config.yaml')

        logging.config.dictConfig(config['logging'])
        logger = logging.getLogger(__name__)
        logger.info("--- Starting Pflanzenschutz Report Generation ---")

        # --- Initialize Components ---
        logger.info("Initializing components...")
        static_loader = StaticDataLoader(
            config['paths']['static_data_path'], 
            config['thresholds']['t1_factor']
        )

        # --- Fetch data ---
        logger.info("--- Fetching Data ---")
        with Driver(download_dir=config['paths']['download_dir'], user_dir=config['paths']['user_dir'], headless=config['driver']['run_headless']) as driver:

            sm_client = SmartFarmerClient(
                driver, 
                config['sm_user'], 
                config['sm_pwd'], 
                config['paths']['download_dir']
            )
            
            try:
                smartfarmer_data = sm_client.fetch_report_data(config['general']['year'])
            except Exception as e:
                logger.critical(f"Failed to fetch SmartFarmer data: {e}")
                raise
            
        processor = DataProcessor(config, None) # Static data loaded later
        reporter_instance = Reporter(config) # Initialize reporter
        logger.info("Components initialized.")
        
        if smartfarmer_data.empty:
            logger.critical("SmartFarmer data is empty or missing 'Datum' column. Skipping SBR fetch.")
            sbr_data = None
        else:
            sm_dates = pd.to_datetime(smartfarmer_data['Datum'], format="%d/%m/%Y", errors='coerce').dropna().sort_values()
            min_date = sm_dates.min()
            max_date = datetime.datetime.now(tz=timezone('Europe/Rome'))
            
            # Check if min_date has timezone, add if necessary
            if min_date.tzinfo is None:
                min_date = min_date.tz_localize('Europe/Rome')
            
            try:
                logger.info(f"Fetching SBR data from {min_date.strftime('%Y-%m-%d %H:%M')} to {max_date.strftime('%Y-%m-%d %H:%M')}.")
                with SBR(config['sbr_user'], config['sbr_pwd']) as client:
                    sbr_data = client.get_stationdata(
                        station_id="103",
                        start=min_date,
                        end=max_date,
                        type='meteo'
                    )
            except Exception as e:
                sbr_data = None
                logger.warning(f"Failed to fetch SBR data: {e}. Proceeding without rainfall data.")

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

        logger.info("--- Reporting Complete ---")

    # --- Error Handling ---
    except Exception as e:
        logger.critical(f"Report generation failed: {e}", exc_info=True)
        # Send failure notification email if possible
        if config:
            subject = f"FEHLER: Pflanzenschutz Report Generation Failed - {datetime.date.today().strftime('%Y-%m-%d')}"
            body = f"<h1>Report Generation Failed</h1><p><strong>Error Type:</strong> {type(e).__name__}</p><p><strong>Message:</strong> {e}</p><p>Check application logs for details.</p>"
            send_mail(
                subject = subject,
                content = body,
                recipients = ['tscholl.simon@gmail.com'],
                host = config['gmail']['host'],
                port = config['gmail']['port'],
                username = config['gmail']['username'],
                password = config['gmail']['password']
            )

    # --- Cleanup ---
    #finally:
        #logger.info("--- Cleaning up resources ---")

# --- Script Entry Point ---
if __name__ == "__main__":
    # No command line args needed here anymore unless you add specific overrides
    run_report_generation()