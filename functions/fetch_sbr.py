import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pandas as pd
import numpy as np
from io import StringIO

def get_br_stationdata(driver, station_id = "103", months = np.arange(4, 9), user = None, pwd = None):

    ## Open Browser
    driver.get('https://www3.beratungsring.org/')

    ## Log in (if needed)
    if driver.find_elements(By.XPATH, '//a[@class="login-link"]'):
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

    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[normalize-space()="Mein SBR"]'))).click()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[6]/ul/li[5]/a'))).click()
    driver.switch_to.window(driver.window_handles[-1])

    year = "2024"

    data_concat = []
    for month in months:

        driver.get(f'https://www.beratungsring.org/beratungsring/list_wetterdaten.php?tyid=105&L=0&ricstaz={station_id}&ricmeteo=1&ricyear={year}&ricmonth={month}&ricday=--')
        time.sleep(5)

        tbl_html = driver.find_element(By.XPATH, "//*/table[@class='searchResults maintable']")
        header = pd.read_html(StringIO(tbl_html.get_attribute('outerHTML')), header = None, skiprows = 1, decimal=',', thousands='.')[0].loc[0].values
        data = pd.read_html(StringIO(tbl_html.get_attribute('outerHTML')), header = None, skiprows = 3, decimal=',', thousands='.')[0]
        data.drop(data.tail(1).index,inplace=True) 
        data.columns = header

        cols_float = data.columns.difference(['Windricht.'])
        data[cols_float] = data[cols_float].astype(float)
        data['Datum'] = pd.to_datetime(data['Tag'].astype(int).astype(str) + '/' + str(month) + '/' + year, format = '%d/%m/%Y')

        data_concat.append(data)
    data_concat = pd.concat(data_concat).sort_values('Datum')

    print('SBR Wetterdaten heruntergeladen!')
    return(data_concat)
