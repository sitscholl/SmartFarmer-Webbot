import pandas as pd
import numpy as np
import re
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from .utils import wait_for_page_stability, wait_for_download, validate_date
import logging

logger = logging.getLogger(__name__)

def export_sbr(driver, start, end, station_name, user = None, pwd = None, download_dir = None):

    validate_date(start)
    validate_date(end)

    if isinstance(station_name, str):
        station_name = [station_name]

    logger.info('Lade Beratungsring Webseite')
    ## Open Browser
    driver.get('https://www3.beratungsring.org/')

    # Wait for the page to stabilize
    if not wait_for_page_stability(driver, check_interval=2, timeout=30):
        logger.warning("Beratungsring landing page did not stabilize within timeout.")
        sys.exit()

    ## Log in (if needed)
    if driver.find_elements(By.XPATH, '//span[normalize-space()="Login"]'):

        if not user or not pwd:
            raise ValueError(">SBR login required but username or password not provided.")

        driver.find_element(By.XPATH, '//a[@class="login-link"]').click()
        ##Insert Email
        driver.find_element(By.XPATH, '//input[@id="s_username"]').send_keys(user)
        ##Insert Password
        driver.find_element(By.XPATH, '//input[@id="s_password"]').send_keys(pwd)
        ##Press Anmelden
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()

        logger.info('SBR Anmeldung erfolgreich.')
    else:
        logger.info('Bereits bei SBR angemeldet.')

    logger.debug('Opening Mein SBR')
    driver.find_element(By.XPATH, '//span[normalize-space()="Mein SBR"]').click()
    driver.find_element(By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[6]/ul/li[3]/a').click()
    driver.switch_to.window(driver.window_handles[-1])

    logger.info('Lade SBR Stationsdaten.')
    driver.get("https://www.beratungsring.org/beratungsring/export_wetterdaten.php?tyid=207&L=0")

    ##End date
    driver.find_element(By.ID, "datepicker_to").clear()
    driver.find_element(By.ID, "datepicker_to").send_keys(end)

    ##Start date
    driver.find_element(By.ID, "datepicker_from").clear()
    driver.find_element(By.ID, "datepicker_from").send_keys(start)

    ##Select Format
    st_select = Select(driver.find_element(By.NAME, 'ExportFormat'))
    st_select.select_by_visible_text('CSV-Datei')

    st_select = Select(driver.find_element(By.NAME, 'st_id'))

    for snam in station_name:
        ##Select station
        st_select.select_by_visible_text(snam)

        ##Export
        driver.find_element(By.NAME, "submit").click()

        #Make sure download finishes
        dfile = wait_for_download(download_dir, f"{snam.replace(' ', '_')}.csv")
        logger.info(f'Wetterdaten für station {snam} heruntergeladen.')
            
    return([f"{i.replace(' ', '_')}.csv" for i in station_name])

def open_sbr_export(path):

    tbl = pd.read_csv(path, sep = ';', decimal=',').dropna(how = 'all', axis = 1)
    tbl['datetime'] = pd.to_datetime(tbl["wet_data"] + " " + tbl["wet_ora"], format = '%Y-%m-%d %S:%H:%M')

    tbl.rename(columns = lambda x: re.sub('^wet_', '', x), inplace = True)
    tbl.drop(['data', 'ora', 'status', 't_2m_min', 't_2m_max', 'luftfeucht_min', 'luftfeucht_max', 'v_wind_max'], axis = 1, inplace = True)
    tbl = tbl[['datetime', 'wst_codice', *[i for i in np.sort(tbl.columns) if i not in  ['datetime', 'wst_codice']]]]

    scale_cols = ['niederschl', *[col for col in tbl if any([col.startswith(i) for i in ['bt_', 't_', 'tf_', 'tt_']])]]
    tbl[scale_cols] = tbl[scale_cols] / 10

    return(tbl)

##Old function to extract sbr-data
# def get_br_stationdata(driver, jahr, station_id = "103", months = np.arange(4, 9), user = None, pwd = None):

#     ## Open Browser
#     driver.get('https://www3.beratungsring.org/')

#     ##Wait for page to be loaded
#     psource = driver.execute_script("return document.documentElement.outerHTML")
#     time.sleep(2)
#     while True:
#         psource_new = driver.execute_script("return document.documentElement.outerHTML")
#         if psource != psource_new:
#             psource = psource_new
#             time.sleep(2)
#         else:
#             break

#     ## Log in (if needed)
#     if driver.find_elements(By.XPATH, '//span[normalize-space()="Login"]'):

#         driver.find_element(By.XPATH, '//a[@class="login-link"]').click()
#         ##Insert Email
#         driver.find_element(By.XPATH, '//input[@id="s_username"]').send_keys(user)
#         ##Insert Password
#         driver.find_element(By.XPATH, '//input[@id="s_password"]').send_keys(pwd)
#         ##Press Anmelden
#         driver.find_element(By.XPATH, '//button[@type="submit"]').click()

#         print('SBR Anmeldung erfolgreich.')

#     WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//span[normalize-space()="Mein SBR"]'))).click()
#     WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div[1]/div[1]/div[6]/ul/li[5]/a'))).click()
#     driver.switch_to.window(driver.window_handles[-1])

#     data_concat = []
#     for month in months:

#         driver.get(f'https://www.beratungsring.org/beratungsring/list_wetterdaten.php?tyid=105&L=0&ricstaz={station_id}&ricmeteo=1&ricyear={jahr}&ricmonth={month}&ricday=--')
        
#         ##Wait for page to be loaded
#         psource = driver.execute_script("return document.documentElement.outerHTML")
#         time.sleep(2)
#         while True:
#             psource_new = driver.execute_script("return document.documentElement.outerHTML")
#             if psource != psource_new:
#                 psource = psource_new
#                 time.sleep(2)
#             else:
#                 break

#         tbl_html = driver.find_element(By.XPATH, "//*/table[@class='searchResults maintable']")
#         header = pd.read_html(StringIO(tbl_html.get_attribute('outerHTML')), header = None, skiprows = 1, decimal=',', thousands='.')[0].loc[0].values
#         data = pd.read_html(StringIO(tbl_html.get_attribute('outerHTML')), header = None, skiprows = 3, decimal=',', thousands='.')[0]
#         data.drop(data.tail(1).index,inplace=True) 
#         data.columns = header

#         cols_float = data.columns.difference(['Windricht.'])
#         data[cols_float] = data[cols_float].astype(float)
#         data['Datum'] = pd.to_datetime(data['Tag'].astype(int).astype(str) + '/' + str(month) + '/' + str(jahr), format = '%d/%m/%Y')

#         data_concat.append(data)
#         print(f'Daten für Station {station_id}, monat {month} und Jahr {jahr} heruntergeladen.')
#     data_concat = pd.concat(data_concat).sort_values('Datum')

#     print('SBR Wetterdaten heruntergeladen!')

#     return(data_concat)