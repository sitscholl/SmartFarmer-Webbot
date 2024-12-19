from xlsx2csv import Xlsx2csv
import numpy as np
import pandas as pd
from pathlib import Path
import datetime

def reformat_tbl(dir):

    files = list(Path(dir).glob("*.xlsx"))
    csv_name = str(files[-1]).replace('.xlsx', '.csv')
    Xlsx2csv(str(files[-1]), outputencoding="latin-1").convert(csv_name)

    tbl = pd.read_csv(csv_name, encoding = 'latin-1')
    tbl['Datum'] = pd.to_datetime(tbl['Datum'], format = "%d/%m/%Y")
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Yaravita Stopit"]), 'Ca-Düngung', tbl['Grund'])
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Epso Combitop", "Epso Top"]), 'Bittersalz', tbl['Grund'])

    tbl['Anlage'] = tbl['Anlage'].str.replace('Neuacker Klein', 'Neuacker')
    tbl[['Wiese', 'Sorte']] = tbl['Anlage'].str.split(' ', expand = True).iloc[:,0:2]

    tbl['Grund'] = tbl['Grund'].str.split(', ')
    tbl = tbl.explode('Grund')

    last_dates = tbl.groupby(['Wiese', 'Sorte', 'Mittel', 'Grund'], as_index = False)['Datum'].max()
    last_dates = last_dates.loc[last_dates['Grund'].isin(["Apfelmehltau", "Apfelschorf", "Ca-Düngung", "Bittersalz"])]

    last_dates['Tage'] = np.floor((datetime.datetime.now() - last_dates['Datum']) / datetime.timedelta(days = 1)) #transform to unit of days

    return(last_dates)
    