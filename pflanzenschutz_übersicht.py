import numpy as np
import pandas as pd
from pathlib import Path
import datetime
import platform
import os
import sys
from dotenv import load_dotenv
from xlsx2csv import Xlsx2csv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from functions.fetch_smartfarmer import fetch_smartfarmer
from functions.fetch_sbr import get_br_stationdata
from functions.get_last_dates import get_last_dates
from functions.google import send_mail, send_sheets


##Parameters
jahr = datetime.datetime.now().year - (datetime.datetime.now().month < 3)
default_mm = 30
default_days = 14
mode = 'full'
thresholds = {'Tage': {'Apfelmehltau': 14,
                       'Apfelschorf': 14,
                       'Bittersalz': 21,
                       'Ca-Düngung': 21},
               'Niederschlag': {'Apfelmehltau': 30,
                       'Apfelschorf': 30,
                       'Bittersalz': 30,
                       'Ca-Düngung': 30}}

load_dotenv("credentials.env")
tbl_mittel = pd.read_csv('data/pflanzenschutzmittel.csv', encoding = 'latin-1')
tbl_mittel['Behandlungsintervall'] = default_days #replace with actual Behandlungsintervall per sorte that is joined to tbl_mittel

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
    download_dir = f"{Path.cwd()}\\downloads"
    user_dir = f"{Path.cwd()}\\user_dir"
else:
    download_dir = 'downloads'
    user_dir = 'user_dir'

options.add_argument(f"user-data-dir={user_dir}")
prefs = {
    "download.default_directory": download_dir,
    "download.directory_upgrade": True,
    "download.prompt_for_download": False,
}
options.add_experimental_option("prefs", prefs)

## Open Browser
driver = webdriver.Chrome(options=options)

# Set timezone
if platform.uname().system != 'Windows':
    tz_params = {'timezoneId': 'Europe/Rome'}
    driver.execute_cdp_cmd('Emulation.setTimezoneOverride', tz_params)

## Download table from smartfarmer
try:
    fetch_smartfarmer(
        driver,
        jahr,
        user=os.environ.get("SM_USERNAME"),
        pwd=os.environ.get("SM_PASSWORD"),
        download_dir=download_dir,
    )
except Exception as e:
    print('Smartfarmer Download Fehlgeschlagen.')
    print(e)
    driver.save_screenshot(f'SmartFarmer_Error_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.png')
    
    sys.exit()

## Open in pandas
filename = sorted(list(Path(download_dir).glob('*.xlsx')), key = lambda x: x.stat().st_ctime)[-1]
csv_name = str(filename).replace('.xlsx', '.csv')
Xlsx2csv(filename, outputencoding="latin-1").convert(csv_name)
tbl_sm = pd.read_csv(csv_name, encoding = 'latin-1')

## Delete downloaded files
filename.unlink()
Path(csv_name).unlink()

## Calculate last date of Behandlung
last_dates = get_last_dates(tbl_sm)
last_dates = last_dates.merge(tbl_mittel, on = 'Mittel', how = 'left')

## Fill missing values
mittel_fehlend = np.sort(last_dates.loc[last_dates['Regenbestaendigkeit'].isna(), 'Mittel'].unique())
if len(mittel_fehlend) > 0:
    print(f"Für folgende {len(mittel_fehlend)} Mittel wurde keine Regenbeständigkeit in der Mitteldatenbank gefunden und ein Standardwert von {default_mm}mm angenommen: \n{', '.join(mittel_fehlend)}")
last_dates['Regenbestaendigkeit'] = last_dates['Regenbestaendigkeit'].fillna(default_mm)

tage_fehlend = np.sort(last_dates.loc[last_dates['Behandlungsintervall'].isna(), 'Mittel'].unique())
if len(tage_fehlend) > 0:
    print(f"Für folgende {len(tage_fehlend)} Mittel wurde kein Behandlungsintervall in der Mitteldatenbank gefunden und ein Standardwert von {default_days} tagen angenommen: \n{', '.join(tage_fehlend)}")
last_dates['Behandlungsintervall'] = last_dates['Behandlungsintervall'].fillna(default_days)

##Drop entries with multiple Mittel and keep only one with longest?? Regenbestaendigkeit
last_dates = last_dates.sort_values('Regenbestaendigkeit', ascending = False).drop_duplicates(subset = ['Wiese', 'Sorte', 'Grund'])

# Get stationdata from SBR
start_dates = last_dates['Datum'].unique()
months = np.unique([*start_dates.month, datetime.datetime.now().month])

try:
    stationdata = get_br_stationdata(driver, jahr, months = months, user = os.environ.get('SBR_USERNAME'), pwd = os.environ.get('SBR_PASSWORD'))
except Exception as e:
    stationdata = None
    print('Beratungsring download fehlgeschlagen. Niederschlagsdaten nicht verfügbar.')
    print(e)

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

##Reformat table for output (round directly at beginning and use variable to determine precision)
tbl_abs = (
    last_dates.pivot(
        columns="Grund", index=["Wiese", "Sorte"], values=["Tage", "Niederschlag"]
    )
    .round(0)
    .astype(int)
)
tbl_thresh = (
    last_dates.pivot(
        columns="Grund",
        index=["Wiese", "Sorte"],
        values=["Behandlungsintervall", "Regenbestaendigkeit"],
    )
    .rename(columns={"Regenbestaendigkeit": "Niederschlag", "Behandlungsintervall": "Tage"}, level=0)
    .round(0)
    .astype(int)
)
tbl_perc = ((tbl_abs / tbl_thresh) * 100).round(0).astype(int)
tbl_string = tbl_abs.astype(str) + '/' + tbl_thresh.astype(str) + ' (' + tbl_perc.astype(str) + '%)'


##Send to gsheets
send_sheets(tbl_string)

##Send email
user, pwd = os.environ.get('GM_USERNAME'), os.environ.get('GM_APPKEY')
send_mail(tbl_string, tbl_perc, user, pwd)
