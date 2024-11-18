import time
import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fetch_smartfarmer(driver, user = None, pwd = None):

    driver.get('https://app.smartfarmer.it/#/auth/welcome/')
    time.sleep(10) #wait for page to be loaded

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

    WebDriverWait(driver, 20).until(
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
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[contains(normalize-space(), "Erntejahr")]'))).click()
    year_to_download = datetime.datetime.now().year - (datetime.datetime.now().month < 3) #only from march onwards use next year
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, f'//span[normalize-space()="Kalenderjahr {year_to_download}"]'))).click()

    ##Wait for all entries to load, also new journal entries
    time.sleep(10)

    ##Click on download button
    dbutton_xpath = '/html/body/div[1]/div/div[1]/div[1]/div[1]/div/div[2]/div/div[2]/div/div/div[1]/span[2]/span/button[2]'
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, dbutton_xpath))).click()

    time.sleep(10) #Make sure download finishes
    print('SmartFarmer Daten heruntergeladen!')
