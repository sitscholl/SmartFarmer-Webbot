import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pandas as pd
import numpy as np
from io import StringIO

def get_br_stationdata(driver, jahr, station_id = "103", months = np.arange(4, 9), user = None, pwd = None):

    ## Open Browser
    driver.get('https://www3.beratungsring.org/')

    ## Log in (if needed)
    if driver.find_elements(By.XPATH, '//span[normalize-space()="Login"]'):
        try:
            driver.find_element(By.XPATH, '//a[@class="login-link"]').click()
            ##Insert Email
            driver.find_element(By.XPATH, '//input[@id="s_username"]').send_keys(user)
            ##Insert Password
            driver.find_element(By.XPATH, '//input[@id="s_password"]').send_keys(pwd)
            ##Press Anmelden
            driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        except Exception as e:
            print(f'Login ins SBR portal fehlgeschlagen! Stationsdaten konnten nicht heruntergeladen werden. Fehler: \n{e}')
            return(None)

    print('Bei SBR eingeloggt')

    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[normalize-space()="Mein SBR"]'))).click()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[6]/ul/li[5]/a'))).click()
    driver.switch_to.window(driver.window_handles[-1])

    data_concat = []
    for month in months:

        driver.get(f'https://www.beratungsring.org/beratungsring/list_wetterdaten.php?tyid=105&L=0&ricstaz={station_id}&ricmeteo=1&ricyear={jahr}&ricmonth={month}&ricday=--')
        
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

        tbl_html = driver.find_element(By.XPATH, "//*/table[@class='searchResults maintable']")
        header = pd.read_html(StringIO(tbl_html.get_attribute('outerHTML')), header = None, skiprows = 1, decimal=',', thousands='.')[0].loc[0].values
        data = pd.read_html(StringIO(tbl_html.get_attribute('outerHTML')), header = None, skiprows = 3, decimal=',', thousands='.')[0]
        data.drop(data.tail(1).index,inplace=True) 
        data.columns = header

        cols_float = data.columns.difference(['Windricht.'])
        data[cols_float] = data[cols_float].astype(float)
        data['Datum'] = pd.to_datetime(data['Tag'].astype(int).astype(str) + '/' + str(month) + '/' + str(jahr), format = '%d/%m/%Y')

        data_concat.append(data)
        print(f'Daten für Station {station_id}, monat {month} und Jahr {jahr} heruntergeladen.')
    data_concat = pd.concat(data_concat).sort_values('Datum')

    print('SBR Wetterdaten heruntergeladen!')
    return(data_concat)
