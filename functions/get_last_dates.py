import numpy as np
import pandas as pd
import datetime

def get_last_dates(tbl, group_cols = ['Wiese', 'Sorte', 'Mittel', 'Grund']):

    tbl['Datum'] = pd.to_datetime(tbl['Datum'], format = "%d/%m/%Y")
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Yaravita Stopit"]), 'Ca-Düngung', tbl['Grund'])
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Epso Combitop", "Epso Top"]), 'Bittersalz', tbl['Grund'])

    tbl['Anlage'] = tbl['Anlage'].str.replace('Neuacker Klein', 'Neuacker')
    tbl[['Wiese', 'Sorte']] = tbl['Anlage'].str.split(' ', expand = True).iloc[:,0:2]

    tbl['Grund'] = tbl['Grund'].str.split(', ')
    tbl = tbl.explode('Grund')

    last_dates = tbl.groupby(group_cols, as_index = False)['Datum'].max()
    last_dates = last_dates.loc[last_dates['Grund'].isin(["Apfelmehltau", "Apfelschorf", "Ca-Düngung", "Bittersalz"])]

    last_dates['Tage'] = np.floor((datetime.datetime.now() - last_dates['Datum']) / datetime.timedelta(days = 1)) #transform to unit of days

    return(last_dates)
    