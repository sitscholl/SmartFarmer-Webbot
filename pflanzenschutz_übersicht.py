import numpy as np
import pandas as pd
from pathlib import Path
import datetime
import platform
import json
from pytz import timezone
from email.message import EmailMessage
import smtplib

import gspread
from gspread_dataframe import set_with_dataframe

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from functions.fetch_smartfarmer import fetch_smartfarmer
from functions.fetch_sbr import get_br_stationdata
from functions.reformat_tbl import reformat_tbl

##Parameters
jahr = datetime.datetime.now().year - (datetime.datetime.now().month < 3)
thresholds = {'Tage': {'Apfelmehltau': 14,
                       'Apfelschorf': 14,
                       'Bittersalz': 21,
                       'Ca-Düngung': 21},
               'Niederschlag': {'Apfelmehltau': 30,
                       'Apfelschorf': 30,
                       'Bittersalz': 30,
                       'Ca-Düngung': 30}}

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
fetch_smartfarmer(driver, jahr, user = secrets['smartfarmer']['user'], pwd = secrets['smartfarmer']['pwd'], download_dir = download_dir)

## Open in pandas
last_dates = reformat_tbl(download_dir)

##Delete downloaded files
try:
    [i.unlink() for i in Path(download_dir).glob('*[.csv .xlsx]')]
except:
    pass

# Get stationdata from SBR
start_dates = last_dates['Datum'].unique()
months = np.unique([*start_dates.month, datetime.datetime.now().month])

stationdata = get_br_stationdata(driver, jahr, months = months, user = secrets['sbr']['user'], pwd = secrets['sbr']['pwd'])

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

header_line = ["Letzte Aktualisierung: ", datetime.datetime.now(tz = timezone('Europe/Berlin')).replace(microsecond = 0)] + [''] * (len(tbl_pivot.columns)-2)
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

##Send email
überschreitungen = {'Tage': [], 'Niederschlag': []}
for col1, d in thresholds.items():
    for col, thresh in d.items():
        if (tbl_pivot.droplevel(0, axis = 1)[col1][col] > thresh).any():
            überschreitungen[col1].append(col)

if (len(überschreitungen['Tage']) > 0) or (len(last_dates['Niederschlag']) > 0):

    msg = EmailMessage()
    msg["Subject"] = 'Pflanzenschutz Übersicht'
    msg['From'] = 'tscholl.simon@gmail.com'
    msg['To'] = 'tscholl.simon@gmail.com'# 'tscholl.simon@gmail.com, erlhof.latsch@gmail.com'

    order_tage = tbl_pivot.droplevel(0, axis = 1)['Tage'].max(axis = 1).sort_values(ascending = False).index
    tbl_tage = tbl_pivot.loc[order_tage].droplevel(0, axis = 1).set_index(['Wiese', 'Sorte'])['Tage'].astype(int)
    order_n = tbl_pivot.droplevel(0, axis = 1)['Niederschlag'].max(axis = 1).sort_values(ascending = False).index
    tbl_n = tbl_pivot.loc[order_tage].droplevel(0, axis = 1).set_index(['Wiese', 'Sorte'])['Niederschlag']

    msg.set_content(
        f"""\
            <h2>Tage</h2>
            {tbl_tage.to_html()}

            <h2>Niederschlag</h2>
            {tbl_n.to_html()}
        """,
        subtype="html",
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
        smtp_server.login(secrets['gmail']['user'], secrets['gmail']['pwd'])
        smtp_server.send_message(msg)
