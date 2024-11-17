import numpy as np
import pandas as pd
from pathlib import Path
import datetime
import platform
import json

import gspread
from gspread_dataframe import set_with_dataframe

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from functions.fetch_smartfarmer import fetch_smartfarmer
from functions.fetch_sbr import get_br_stationdata
from functions.reformat_tbl import reformat_tbl

# Open webpage and load cookies
options = Options()
options.add_argument("--disable-search-engine-choice-screen")
options.add_argument("--start-maximized")

if platform.uname().system != 'Windows':
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--no-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--dns-prefetch-disable')

if platform.uname().system == 'Windows':
    options.add_argument(f"user-data-dir={Path.cwd()}\\user_dir")

download_dir = f"{Path.cwd()}\\downloads"
prefs = {
    "download.default_directory": download_dir,
    "download.directory_upgrade": True,
    "download.prompt_for_download": False,
}
options.add_experimental_option("prefs", prefs)

with open('secrets.json') as f:
    secrets = json.load(f)

## Open Browser
driver = webdriver.Chrome(options=options)

# Set timezone
if platform.uname().system != 'Windows':
    tz_params = {'timezoneId': 'Europe/Rome'}
    driver.execute_cdp_cmd('Emulation.setTimezoneOverride', tz_params)

## Download table from smartfarmer
fetch_smartfarmer(driver, user = secrets['smartfarmer']['user'], pwd = secrets['smartfarmer']['pwd'])

## Open in pandas
last_dates = reformat_tbl(download_dir)

##Delete downloaded files
try:
    [i.unlink() for i in Path(download_dir).glob('*[.csv .xlsx]')]
except:
    pass

#Get stationdata from SBR
start_dates = last_dates['Datum'].unique()
months = np.unique([*start_dates.month, datetime.datetime.now().month])

stationdata = get_br_stationdata(driver, months = months, user = secrets['sbr']['user'], pwd = secrets['sbr']['pwd'])

if stationdata is not None:
    sums = []
    for start in start_dates:
        sums.append(stationdata.loc[(stationdata['Datum'] >= start) & (stationdata['Datum'] < datetime.datetime.now()), 'Niederschl. (mm)'].sum())
    sums = pd.DataFrame({'Datum': start_dates, 'Niederschlag': sums})

    last_dates = last_dates.merge(sums, on = 'Datum', how = 'left')

else:
    last_dates['Niederschlag'] = np.nan

## Close driver
driver.quit()

# Pivot
tbl_pivot = last_dates.pivot(columns = 'Grund', index = ['Wiese', 'Sorte'], values = ['Tage', 'Niederschlag']).reset_index()

header_line = ["Letzte Aktualisierung: ", datetime.datetime.now().replace(microsecond = 0)] + [''] * (len(tbl_pivot.columns)-2)
column_index = [(i, *j) for i, j in zip(header_line, tbl_pivot.columns.copy())]
tbl_pivot.columns = pd.MultiIndex.from_tuples(column_index)

# Send to google sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

client = gspread.service_account(filename = 'gcloud_key.json', scopes = scope)
gtable = client.open("Behandlungsübersicht")
ws = gtable.worksheet("Behandlungsübersicht")

set_with_dataframe(worksheet=ws, dataframe=tbl_pivot, include_index=False, include_column_header=True, resize=True)
print('Tabelle an Google Sheets gesendet!')