import time
import datetime
import numpy as np
import pandas as pd
import sys
from pathlib import Path
from pytz import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils import wait_for_page_stability, wait_and_click, wait_and_send_keys
import logging

logger = logging.getLogger(__name__)

def fetch_smartfarmer(driver, jahr, user = None, pwd = None, download_dir = None):
    """
    Logs into SmartFarmer, navigates to the reports section, selects the specified year,
    triggers a download, and waits for the download to complete.
    """
    logger.info('Lade SmartFarmer webseite')
    driver.get('https://app.smartfarmer.it/#/auth/welcome/')

    # Wait for the page to stabilize
    if not wait_for_page_stability(driver, check_interval=2, timeout=30):
        logger.warning("SmartFarmer landing page did not stabilize within timeout.")
        sys.exit()

    # Check if login is needed by looking for a specific login prompt.
    if "Bitte geben Sie Ihre E-Mail Adresse ein" in driver.page_source:

        if not user or not pwd:
            raise ValueError("SmartFarmer login required but username or password not provided.")

        ##Insert Email
        wait_and_send_keys(driver, '//input[@type="email"]', user)
        wait_and_click(driver, '//button[normalize-space()="weiter ►"]')

        ##Insert Password
        wait_and_send_keys(driver, '//input[@type="password"]', pwd)
        wait_and_click(driver, '//button[normalize-space()="login"]')

        logger.info('SmartFarmer Anmeldung erfolgreich')
    else:
        logger.info('SmartFarmer bereits angemeldet.')

    # Wait until one of the expected elements is clickable (could be a pop-up or main menu)
    WebDriverWait(driver, 30).until(
        EC.any_of(
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="später"]')),
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="jetzt nicht"]')),
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Berichte"]')),
        )
    )

    ##Close pop-ups if present
    if "App aktualisiert" in driver.page_source:
        driver.find_element(By.XPATH, '//button[normalize-space()="später"]').click()
    if "SmartFarmer installieren?" in driver.page_source:
        driver.find_element(By.XPATH, '//button[normalize-space()="jetzt nicht"]').click()

    # Navigate through the menu to open the reports section
    wait_and_click(driver, '//button[normalize-space()="Berichte"]')
    wait_and_click(driver, '//div[normalize-space()="Maßnahmen"]')
    wait_and_click(driver, '//div[normalize-space()="Liste"]')

    # Select the desired year (using 'Kalenderjahr')
    WebDriverWait(driver, 20).until(EC.any_of(
        EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Erntejahr")]')),
        EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Kalenderjahr")]'))
        )
    ).click()
    year_xpath = f'//span[normalize-space()="Kalenderjahr {jahr}"]'
    wait_and_click(driver, year_xpath)

    # Wait for all entries to load
    if not wait_for_page_stability(driver, check_interval=2, timeout=30):
        logger.warning("SmartFarmer download page did not stabilize within timeout.")
        sys.exit()

    ##Click on download button
    dbutton_xpath = '/html/body/div[1]/div/div[1]/div[1]/div[1]/div/div[2]/div/div[2]/div/div/div[1]/span[2]/span/button[2]'
    wait_and_click(driver, dbutton_xpath)

    #Make sure download finishes
    if download_dir is not None:
        download_complete = False
        start_time = datetime.datetime.now(tz = timezone('Europe/Berlin'))
        while (datetime.datetime.now(tz = timezone('Europe/Berlin')) - start_time).total_seconds() < 60:
            dfiles = list(Path(download_dir).glob('*.xlsx'))
            if len(dfiles) > 0:
                newest_ctime = datetime.datetime.fromtimestamp(dfiles[-1].stat().st_ctime, tz = timezone('Europe/Berlin'))
                if (datetime.datetime.now(tz = timezone('Europe/Berlin')) - newest_ctime).total_seconds() < 10:
                    download_complete = True
                    break
        if not download_complete:
            logger.warning("Download might not have completed within the expected time.")
            sys.exit()
    else:
        time.sleep(10)
    logger.info('SmartFarmer Daten heruntergeladen!')

def reformat_sm_data(tbl):
    """
    Reformats SmartFarmer data:
      - Converts the 'Datum' column to datetime.
      - Normalizes 'Grund' values based on 'Mittel'.
      - Adjusts 'Anlage' names and extracts 'Wiese' and 'Sorte'.
      - Splits and explodes the 'Grund' field.
    """
    tbl['Datum'] = pd.to_datetime(tbl['Datum'], format = "%d/%m/%Y")
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Yaravita Stopit"]), 'Ca-Düngung', tbl['Grund'])
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Epso Combitop", "Epso Top"]), 'Bittersalz', tbl['Grund'])

    tbl['Anlage'] = tbl['Anlage'].str.replace('Neuacker Klein', 'Neuacker')
    tbl['Wiese'] = tbl['Anlage'].str.split(' ', expand = True).iloc[:,0]
    tbl['Sorte'] = tbl['Anlage'].str.extract(r"(?<=) (.+) (?=)[0-9]{4}")

    tbl['Grund'] = tbl['Grund'].str.split(', ')
    tbl = tbl.explode('Grund')

    return(tbl)
