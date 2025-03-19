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
from jinja2 import Environment, FileSystemLoader
import spINT
import argparse
from tempfile import TemporaryDirectory
import logging
import logging.config

logging.config.fileConfig(".config/logging.conf", disable_existing_loggers=False)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Create the parser
parser = argparse.ArgumentParser(description='Berechne den Zeitraum pro Wiese seit der letzten Behandlung.')

# Add the arguments
parser.add_argument('-j', '--jahr', type=int, default=2025,
                    help='the year to process')
parser.add_argument('--default_mm', type=int, default=30,
                    help='default value for mm')
parser.add_argument('--default_days', type=int, default=14,
                    help='default value for days')
parser.add_argument('--t1_factor', type=float, default=0.75,
                    help='factor for t1')
parser.add_argument('-d', '--download_dir', default = TemporaryDirectory().name, help = 'Download directory')
parser.add_argument('-u', '--user_dir', default = "user_dir", help = 'Directory with user data from chrome.')
parser.add_argument('-he', '--headless', action = 'store_false', help = 'Disable headless browser.')

# Parse the arguments
args = parser.parse_args()

jahr = args.jahr
default_mm = args.default_mm
default_days = args.default_days
t1_factor = args.t1_factor
download_dir = args.download_dir
user_dir = args.user_dir

# Create download directory
Path(download_dir).mkdir(exist_ok = True, parents = True)

logger.info(f"Programm gestartet: Jahr = {jahr}, default_mm = {default_mm}, default_tage = {default_days}, t1_factor = {t1_factor}")

load_dotenv("credentials.env")

tbl_regenbestaendigkeit = spINT.load_regenbestaendigkeit("data/regenbestaendigkeit.csv", t1_factor = t1_factor)
tbl_sortenanfaelligkeit = spINT.load_sortenanfaelligkeit("data/sortenanfaelligkeit.csv")
tbl_behandlungsintervall = spINT.load_behandlungsintervall("data/behandlungsintervall.csv", tbl_sortenanfaelligkeit)

## On windows, full path to user_dir needed
if platform.uname().system == 'Windows':
    user_dir = f"{Path.cwd()}\\user_dir"

##Start drivers
driver = spINT.init_driver(download_dir=download_dir, user_dir=user_dir, headless=args.headless)

## Download table from smartfarmer
try:
    spINT.fetch_smartfarmer(
        driver,
        jahr,
        user=os.environ.get("SM_USERNAME"),
        pwd=os.environ.get("SM_PASSWORD"),
        download_dir=download_dir,
    )
except Exception as e:
    logger.error('SmartFarmer download fehlgeschlagen.', exc_info=True)
    sys.exit()

logger.info('Formatiere SmartFarmer Tabelle')
## Open in pandas
filename = sorted(list(Path(download_dir).glob('*.xlsx')), key = lambda x: x.stat().st_ctime)[-1]
csv_name = str(filename).replace('.xlsx', '.csv')
Xlsx2csv(filename, outputencoding="latin-1").convert(csv_name)
tbl_sm = pd.read_csv(csv_name, encoding = 'latin-1')

## Calculate last date of Behandlung
tbl_sm_re = spINT.reformat_sm_data(tbl_sm.copy())
last_dates = tbl_sm_re.groupby(['Wiese', 'Sorte', 'Mittel', 'Grund'], as_index = False)['Datum'].max()
last_dates = last_dates.loc[last_dates['Grund'].isin(["Apfelmehltau", "Apfelschorf", "Ca-Düngung", "Bittersalz"])]
last_dates['Tage'] = np.floor((datetime.datetime.now() - last_dates['Datum']) / datetime.timedelta(days = 1))

## Add Regenbeständigkeit
last_dates = last_dates.merge(tbl_regenbestaendigkeit[['Mittel', 'Regenbestaendigkeit_min', 'Regenbestaendigkeit_max']], on = 'Mittel', how = 'left', validate = 'many_to_one')

mittel_fehlend = np.sort(last_dates.loc[last_dates['Regenbestaendigkeit_max'].isna(), 'Mittel'].unique())
if len(mittel_fehlend) > 0:
    mittel_join = "\t" + '\n\t'.join(mittel_fehlend)
    logger.warning(f"Für folgende {len(mittel_fehlend)} Mittel wurde keine Regenbeständigkeit in der Mitteldatenbank gefunden und ein Standardwert von {default_mm}mm angenommen: \n{mittel_join}")
last_dates['Regenbestaendigkeit_max'] = last_dates['Regenbestaendigkeit_max'].fillna(default_mm)
last_dates['Regenbestaendigkeit_min'] = last_dates['Regenbestaendigkeit_min'].fillna((last_dates['Regenbestaendigkeit_max'] * t1_factor))

## Add Behandlungsintervall
last_dates = last_dates.merge(tbl_behandlungsintervall, on = ['Mittel', 'Sorte'], how = 'left', validate = 'many_to_one')

tage_fehlend = np.sort(last_dates.loc[last_dates['Behandlungsintervall_max'].isna(), 'Mittel'].unique())
if len(tage_fehlend) > 0:
    tage_join = "\t" + '\n\t'.join(mittel_fehlend)
    logger.warning(f"Für folgende {len(tage_fehlend)} Mittel wurde kein Behandlungsintervall in der Mitteldatenbank gefunden und ein Standardwert von {default_days} tagen angenommen: \n{tage_join}")
last_dates['Behandlungsintervall_max'] = last_dates['Behandlungsintervall_max'].fillna(default_days)
last_dates['Behandlungsintervall_min'] = last_dates['Behandlungsintervall_min'].fillna((last_dates['Behandlungsintervall_max'] * t1_factor).round(0))

##Get last Spritzung for each field and reason. 
##If multiple mittel with same reason on same day, keep one with longest regenbestaendigkeit and behandlungsintervall
last_dates = last_dates.sort_values(
    ["Datum", "Regenbestaendigkeit_max", "Behandlungsintervall_max"], ascending=False
).drop_duplicates(subset=["Wiese", "Sorte", "Grund"], keep="first")

# Get stationdata from SBR
start_dates = last_dates['Datum'].unique()

try:
    sbr_start = last_dates['Datum'].min().strftime('%d.%m.%Y')
    sbr_end = min([datetime.datetime(jahr,12,31), datetime.datetime.now()]).strftime('%d.%m.%Y')
    sbr_files = spINT.export_sbr(driver, start = sbr_start, end = sbr_end, station_name = 'Latsch 1', user = os.environ.get('SBR_USERNAME'), pwd = os.environ.get('SBR_PASSWORD'), download_dir = download_dir)
    stationdata = pd.concat([spINT.open_sbr_export(Path(download_dir, i)) for i in sbr_files])
    
except Exception as e:
    stationdata = None
    logger.error('Beratungsring download fehlgeschlagen. Niederschlagsdaten nicht verfügbar.', exc_info = True)
    # driver.save_screenshot(f'screenshots/SBR_Error_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.png')

if stationdata is not None:
    logger.info('Berechne Niederschlagssummen')
    sums = []
    for start in start_dates:
        sums.append(stationdata.loc[(stationdata['datetime'] >= start) & (stationdata['datetime'] < datetime.datetime.now()), 'niederschl'].sum())
    sums = pd.DataFrame({'Datum': start_dates, 'Niederschlag': sums})

    last_dates = last_dates.merge(sums, on = 'Datum', how = 'left')
else:
    last_dates['Niederschlag'] = np.nan

## Close driver
driver.quit()

##Reformat table for output
logger.info('Formatiere output Tabelle')
val_cols = list( set(['Tage', 'Niederschlag']).intersection(last_dates.dropna(how = 'all', axis = 1).columns) )
tbl_abs = (
    last_dates.pivot(
        columns="Grund", index=["Wiese", "Sorte"], values=val_cols
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
)[val_cols]
tbl_thresh_min = (
    last_dates.pivot(
        columns="Grund",
        index=["Wiese", "Sorte"],
        values=["Behandlungsintervall_min", "Regenbestaendigkeit_min"],
    )
    .rename(columns={"Regenbestaendigkeit_min": "Niederschlag", "Behandlungsintervall_min": "Tage"}, level=0)
    .round(0)
    .astype(int)
)[val_cols]
tbl_mittel = (
    last_dates.pivot(
        columns="Grund", index=["Wiese", "Sorte"], values="Mittel"
    )
)
tbl_perc = ((tbl_abs / tbl_thresh_max) * 100).round(0).astype(int)
tbl_string = tbl_abs.astype(str) + '/' + tbl_thresh_max.astype(str) + ' (' + tbl_mittel + ')'

# Path("results").mkdir(parents=True, exist_ok=True)
# tbl_string.to_csv('results/tbl_string.csv')

# tbl_formatted = format_tbl(tbl_string, tbl_abs, t1 = tbl_thresh_min, t2 = tbl_thresh_max, caption=f"Letzte Aktualisierung: {datetime.datetime.now(tz = timezone('Europe/Berlin')):%Y-%m-%d %H:%M}")

##Send to gsheets
# send_sheets(tbl_string)

##Send email
logger.info('Sende email')
params = np.unique(tbl_string.columns.get_level_values(0))
environment = Environment(loader=FileSystemLoader("template/"))
template = environment.get_template("mail.html")
mail_body = template.render(
    date=datetime.datetime.now(tz = timezone('Europe/Berlin')).strftime("%Y-%m-%d %H:%M"),
    tables_dict = {i: spINT.format_tbl(tbl_string[i], tbl_abs[i], tbl_thresh_min[i], tbl_thresh_max[i]).to_html(classes = "tb") for i in params},
)

user, pwd = os.environ.get('GM_USERNAME'), os.environ.get('GM_APPKEY')
spINT.send_mail(mail_body, user, pwd, recipients = ['tscholl.simon@gmail.com', 'erlhof.latsch@gmail.com'])

logger.info('Aktualisierung Behandlungsübersicht abgeschlossen.')