import numpy as np
import pandas as pd
from pathlib import Path
import datetime
import platform
import os
import sys
from dotenv import load_dotenv
from xlsx2csv import Xlsx2csv
from pytz import timezone

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from functions.fetch_smartfarmer import fetch_smartfarmer
from functions.fetch_sbr import get_br_stationdata
from functions.get_last_dates import get_last_dates
from functions.google import send_mail, send_sheets

from functions.format_tbl import format_tbl

##Parameters
jahr = datetime.datetime.now().year - (datetime.datetime.now().month < 3)
default_mm = 30
default_days = 14
t1_factor = 0.75
jahreszeit = 'Frühjahr'#['Frühjahr', 'Vorblüte', 'Nachblüte', 'Sommer'] #determine dynamically from current date or from date of spritzung?
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
tbl_regenbestaendigkeit = pd.read_csv('data/regenbestaendigkeit.csv', encoding = 'latin-1').rename(columns={'Regenbestaendigkeit': 'Regenbestaendigkeit_max'})
tbl_regenbestaendigkeit['Regenbestaendigkeit_min'] = tbl_regenbestaendigkeit['Regenbestaendigkeit_max'] * t1_factor
# tbl_mittel['Behandlungsintervall'] = default_days #replace with actual Behandlungsintervall per sorte that is joined to tbl_mittel
tbl_anfaelligkeit = pd.read_csv("data/sortenanfaelligkeit.csv", encoding="latin-1")
tbl_behandlungsintervall = (
    pd.read_csv("data/behandlungsintervall.csv", encoding="latin-1", sep="\t")
    .melt(
        id_vars=["Mittel", "Jahreszeit", "Range"],
        var_name="Mehltauanfälligkeit",
        value_name="Behandlungsintervall",
    )
    .merge(tbl_anfaelligkeit, on="Mehltauanfälligkeit")
    .query(f"Jahreszeit == '{jahreszeit}'")
    .pivot(columns = 'Range', values = 'Behandlungsintervall', index = ['Mittel', 'Sorte'])
    .reset_index()
    .rename(columns = {'min': 'Behandlungsintervall_min', 'max': 'Behandlungsintervall_max'})
)


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
last_dates = get_last_dates(tbl_sm.copy()) #move calculation of Tage out of function
last_dates['Tage'] = np.floor((datetime.datetime.now() - last_dates['Datum']) / datetime.timedelta(days = 1)) #transform to unit of days

## Add Regenbeständigkeit
last_dates = last_dates.merge(tbl_regenbestaendigkeit[['Mittel', 'Regenbestaendigkeit_min', 'Regenbestaendigkeit_max']], on = 'Mittel', how = 'left', validate = 'many_to_one')

mittel_fehlend = np.sort(last_dates.loc[last_dates['Regenbestaendigkeit_max'].isna(), 'Mittel'].unique())
if len(mittel_fehlend) > 0:
    print(f"Für folgende {len(mittel_fehlend)} Mittel wurde keine Regenbeständigkeit in der Mitteldatenbank gefunden und ein Standardwert von {default_mm}mm angenommen: \n{', '.join(mittel_fehlend)}")
last_dates['Regenbestaendigkeit_max'] = last_dates['Regenbestaendigkeit_max'].fillna(default_mm)
last_dates['Regenbestaendigkeit_min'] = last_dates['Regenbestaendigkeit_min'].fillna((last_dates['Regenbestaendigkeit_max'] * t1_factor))

## Add Behandlungsintervall
last_dates = last_dates.merge(tbl_behandlungsintervall[['Mittel', 'Sorte', 'Behandlungsintervall_min', 'Behandlungsintervall_max']], on = ['Mittel', 'Sorte'], how = 'left', validate = 'many_to_one')

tage_fehlend = np.sort(last_dates.loc[last_dates['Behandlungsintervall_max'].isna(), 'Mittel'].unique())
if len(tage_fehlend) > 0:
    print(f"Für folgende {len(tage_fehlend)} Mittel wurde kein Behandlungsintervall in der Mitteldatenbank gefunden und ein Standardwert von {default_days} tagen angenommen: \n{', '.join(tage_fehlend)}")
last_dates['Behandlungsintervall_max'] = last_dates['Behandlungsintervall_max'].fillna(default_days)
last_dates['Behandlungsintervall_min'] = last_dates['Behandlungsintervall_min'].fillna((last_dates['Behandlungsintervall_max'] * t1_factor).round(0))

##Drop entries with multiple Mittel and keep only one with longest?? Regenbestaendigkeit
last_dates = last_dates.sort_values('Regenbestaendigkeit_max', ascending = False).drop_duplicates(subset = ['Wiese', 'Sorte', 'Grund'])

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
tbl_thresh_max = (
    last_dates.pivot(
        columns="Grund",
        index=["Wiese", "Sorte"],
        values=["Behandlungsintervall_max", "Regenbestaendigkeit_max"],
    )
    .rename(columns={"Regenbestaendigkeit_max": "Niederschlag", "Behandlungsintervall_max": "Tage"}, level=0)
    .round(0)
    .astype(int)
)
tbl_thresh_min = (
    last_dates.pivot(
        columns="Grund",
        index=["Wiese", "Sorte"],
        values=["Behandlungsintervall_min", "Regenbestaendigkeit_min"],
    )
    .rename(columns={"Regenbestaendigkeit_min": "Niederschlag", "Behandlungsintervall_min": "Tage"}, level=0)
    .round(0)
    .astype(int)
)
tbl_perc = ((tbl_abs / tbl_thresh_max) * 100).round(0).astype(int)
tbl_string = tbl_abs.astype(str) + '/' + tbl_thresh_max.astype(str) + ' (' + tbl_perc.astype(str) + '%)'

# tbl_formatted = format_tbl(tbl_string, tbl_abs, t1 = tbl_thresh_min, t2 = tbl_thresh_max, caption=f"Letzte Aktualisierung: {datetime.datetime.now(tz = timezone('Europe/Berlin')):%Y-%m-%d %H:%M}")

##Send to gsheets
send_sheets(tbl_string)

##Send email
params = np.unique(tbl_string.columns.get_level_values(0))
caption = f"Letzte Aktualisierung: {datetime.datetime.now(tz = timezone('Europe/Berlin')):%Y-%m-%d %H:%M}"
msg_html = "".join(
    [
    f"""\
    <h2>{param}</h2>
    {format_tbl(tbl_string[param], tbl_abs[param], tbl_thresh_min[param], tbl_thresh_max[param]).to_html()}
    """
    for param in params
    ]
)

user, pwd = os.environ.get('GM_USERNAME'), os.environ.get('GM_APPKEY')
send_mail(msg_html, user, pwd)
