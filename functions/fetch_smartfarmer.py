import time
import datetime
from pathlib import Path
from pytz import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fetch_smartfarmer(driver, jahr, user = None, pwd = None, download_dir = None):

    try:
        driver.get('https://app.smartfarmer.it/#/auth/welcome/')

        ##Wait for page to be loaded
        psource = driver.execute_script("return document.documentElement.outerHTML")
        time.sleep(2)
        while True:
            psource_new = driver.execute_script("return document.documentElement.outerHTML")
            if psource != psource_new:
                psource = psource_new
                time.sleep(2)
            else:
                break

        ## Log into SmartFarmer (if needed)
        if "Bitte geben Sie Ihre E-Mail Adresse ein" in driver.page_source:
            wait = WebDriverWait(driver, 10)

            ##Insert Email
            forward_element = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="weiter ►"]')))
            driver.find_element(By.XPATH, '//input[@type="email"]').send_keys(user)
            forward_element.click()

            ##Insert Password
            login_element = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="login"]')))
            driver.find_element(By.XPATH, '//input[@type="password"]').send_keys(pwd)
            login_element.click()

            print('SmartFarmer Anmeldung erfolgreich')

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

        ##Open Category
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Berichte"]'))).click()
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//div[normalize-space()="Maßnahmen"]'))).click()
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//div[normalize-space()="Liste"]'))).click()

        ##Jahr auswählen
        WebDriverWait(driver, 20).until(EC.any_of(
            EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Erntejahr")]')),
            EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Kalenderjahr")]'))
            )).click()
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, f'//span[normalize-space()="Kalenderjahr {jahr}"]'))).click()

        ##Wait for all entries to load, also new journal entries
        psource = driver.execute_script("return document.documentElement.outerHTML")
        time.sleep(1)
        while True:
            psource_new = driver.execute_script("return document.documentElement.outerHTML")
            if psource != psource_new:
                psource = psource_new
                time.sleep(1)
            else:
                break

        ##Click on download button
        dbutton_xpath = '/html/body/div[1]/div/div[1]/div[1]/div[1]/div/div[2]/div/div[2]/div/div/div[1]/span[2]/span/button[2]'
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, dbutton_xpath))).click()

        #Make sure download finishes
        if download_dir is not None:
            start_time = datetime.datetime.now(tz = timezone('Europe/Berlin'))
            while (datetime.datetime.now(tz = timezone('Europe/Berlin')) - start_time).total_seconds() < 60:
                dfiles = list(Path(download_dir).glob('*.xlsx'))
                if len(dfiles) > 0:
                    newest_ctime = datetime.datetime.fromtimestamp(dfiles[-1].stat().st_ctime, tz = timezone('Europe/Berlin'))
                    if (datetime.datetime.now(tz = timezone('Europe/Berlin')) - newest_ctime).total_seconds() < 10:
                        break
        else:
            time.sleep(10)
        print('SmartFarmer Daten heruntergeladen!')
        return(True)
    except Exception as e:
        print('Fehler beim Herunterladen von SmartFarmer. Screenshot gespeichert')
        print(e)
        driver.save_screenshot(f'SmartFarmer_Error_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.png')
        return(False)
