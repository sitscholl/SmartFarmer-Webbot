import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import pandas as pd
import numpy as np
from io import StringIO
import datetime

def get_br_stationdata(driver, jahr, station_id = "103", months = np.arange(4, 9), user = None, pwd = None):

    ## Open Browser
    driver.get('https://www3.beratungsring.org/')

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

    ## Log in (if needed)
    if driver.find_elements(By.XPATH, '//span[normalize-space()="Login"]'):

        driver.find_element(By.XPATH, '//a[@class="login-link"]').click()
        ##Insert Email
        driver.find_element(By.XPATH, '//input[@id="s_username"]').send_keys(user)
        ##Insert Password
        driver.find_element(By.XPATH, '//input[@id="s_password"]').send_keys(pwd)
        ##Press Anmelden
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()

        print('SBR Anmeldung erfolgreich.')

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

def export_sbr(driver, start, end, station_name, user, pwd):

    ##Validate input dates
    try:
        if start != datetime.datetime.strptime(start, "%d.%m.%Y").strftime('%d.%m.%Y'):
            raise ValueError
    except ValueError:
        raise ValueError(f'Start date needs to be in %d.%m.%Y format. Got {start}')

    try:
        if end != datetime.datetime.strptime(end, "%d.%m.%Y").strftime('%d.%m.%Y'):
            raise ValueError
    except ValueError:
        raise ValueError(f'End date needs to be in %d.%m.%Y format. Got {end}')

    ## Open Browser
    driver.get('https://www3.beratungsring.org/')

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

    ## Log in (if needed)
    if driver.find_elements(By.XPATH, '//span[normalize-space()="Login"]'):

        driver.find_element(By.XPATH, '//a[@class="login-link"]').click()
        ##Insert Email
        driver.find_element(By.XPATH, '//input[@id="s_username"]').send_keys(user)
        ##Insert Password
        driver.find_element(By.XPATH, '//input[@id="s_password"]').send_keys(pwd)
        ##Press Anmelden
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()

        print('SBR Anmeldung erfolgreich.')

    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[normalize-space()="Mein SBR"]'))).click()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[6]/ul/li[5]/a'))).click()
    driver.switch_to.window(driver.window_handles[-1])

    driver.get("https://www.beratungsring.org/beratungsring/export_wetterdaten.php?tyid=207&L=0")

    ##Start date
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "datepicker_from"))).clear()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "datepicker_from"))).send_keys(start)

    ##End date
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "datepicker_to"))).clear()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "datepicker_to"))).send_keys(end)

    ##Select station
    st_select = Select(driver.find_element(By.NAME, 'st_id'))
    st_select.select_by_visible_text(station_name)

    ##Select Format
    st_select = Select(driver.find_element(By.NAME, 'ExportFormat'))
    st_select.select_by_visible_text('CSV-Datei')

    ##Export
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.NAME, "submit"))).click()

    return(f"{station_name.replace(' ', '_')}.csv")

