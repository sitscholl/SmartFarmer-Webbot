import numpy as np
import pandas as pd
import sys
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils import wait_for_page_stability, wait_for_download
from .google import send_mail
from .utils import temporary_implicit_wait
import logging

logger = logging.getLogger(__name__)

def fetch_smartfarmer(driver, jahr, download_dir, user = None, pwd = None):
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
        driver.find_element(By.XPATH, '//input[@type="email"]').send_keys(user)
        driver.find_element(By.XPATH, '//button[normalize-space()="weiter ►"]').click()

        ##Insert Password
        driver.find_element(By.XPATH, '//input[@type="password"]').send_keys(pwd)
        driver.find_element(By.XPATH, '//button[normalize-space()="login"]').click()

        logger.info('SmartFarmer Anmeldung erfolgreich')
    else:
        logger.info('SmartFarmer bereits angemeldet.')

    # Wait until one of the expected elements is clickable (could be a pop-up or main menu)
    logger.debug("Waiting for page to load...")
    with temporary_implicit_wait(driver, 0):
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
    logger.debug('Navigating through menu')
    driver.find_element(By.XPATH, '//button[normalize-space()="Berichte"]').click()
    driver.find_element(By.XPATH, '//div[normalize-space()="Maßnahmen"]').click()
    driver.find_element(By.XPATH, '//div[normalize-space()="Liste"]').click()

    # Select the desired year (using 'Kalenderjahr')
    logger.debug(f'Filtering year {jahr}')
    with temporary_implicit_wait(driver, 0):
        WebDriverWait(driver, 20).until(EC.any_of(
            EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Erntejahr")]')),
            EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Kalenderjahr")]'))
            )
        ).click()
    year_xpath = f'//span[normalize-space()="Kalenderjahr {jahr}"]'
    driver.find_element(By.XPATH, year_xpath).click()

    # Wait for all entries to load
    if not wait_for_page_stability(driver, check_interval=2, timeout=30):
        logger.warning("SmartFarmer download page did not stabilize within timeout.")
        sys.exit()

    ##Click on download button
    if "Keine passenden Einträge gefunden" in driver.page_source:
        msg = f'Keine Einträge für Jahr {jahr} gefunden!'
        logger.warning(msg)
        user, pwd = os.environ.get('GM_USERNAME'), os.environ.get('GM_APPKEY')
        send_mail(msg, user, pwd)
        sys.exit()
    else:
        logger.debug('Downloading SmartFarmer table')
        dbutton_xpath = '/html/body/div[1]/div/div[1]/div[1]/div[1]/div/div[2]/div/div[2]/div/div/div[1]/span[2]/span/button[2]'
        driver.find_element(By.XPATH, dbutton_xpath).click()

    #Make sure download finishes
    dfile = wait_for_download(download_dir, extension = '.xlsx')
    logger.info(f'SmartFarmer Daten heruntergeladen! ({dfile})')

def reformat_sm_data(tbl):
    """
    Reformats SmartFarmer data:
      - Converts the 'Datum' column to datetime.
      - Normalizes 'Grund' values based on 'Mittel'.
      - Adjusts 'Anlage' names and extracts 'Wiese' and 'Sorte'.
      - Splits and explodes the 'Grund' field.
    """
    tbl['Datum'] = pd.to_datetime(tbl['Datum'], format = "%d/%m/%Y")
    tbl['Grund'] = np.where(tbl['Mittel'].str.lower().isin(["yaravita stopit"]), 'Ca-Düngung', tbl['Grund'])
    tbl['Grund'] = np.where(tbl['Mittel'].str.lower().isin(["epso combitop", "epso top"]), 'Bittersalz', tbl['Grund'])
    tbl['Grund'] = np.where(tbl['Mittel'].str.lower().isin(["ats", "supreme n"]), 'Chemisches Ausdünnen', tbl['Grund'])

    tbl['Anlage'] = tbl['Anlage'].str.replace('Neuacker Klein', 'Neuacker')
    tbl['Wiese'] = tbl['Anlage'].str.split(' ', expand = True).iloc[:,0]
    tbl['Sorte'] = tbl['Anlage'].str.extract(r"(?<=) (.+) (?=)[0-9]{4}")

    tbl['Grund'] = tbl['Grund'].str.split(', ')
    tbl = tbl.explode('Grund')

    return(tbl)
