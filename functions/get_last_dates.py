import numpy as np
import pandas as pd

def get_last_dates(tbl, group_cols = ['Wiese', 'Sorte', 'Mittel', 'Grund']):

    tbl['Datum'] = pd.to_datetime(tbl['Datum'], format = "%d/%m/%Y")
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Yaravita Stopit"]), 'Ca-Düngung', tbl['Grund'])
    tbl['Grund'] = np.where(tbl['Mittel'].isin(["Epso Combitop", "Epso Top"]), 'Bittersalz', tbl['Grund'])

    tbl['Anlage'] = tbl['Anlage'].str.replace('Neuacker Klein', 'Neuacker')
    tbl['Wiese'] = tbl['Anlage'].str.split(' ', expand = True).iloc[:,0]
    tbl['Sorte'] = tbl['Anlage'].str.extract(r"(?<=) (.+) (?=)[0-9]{4}")

    tbl['Grund'] = tbl['Grund'].str.split(', ')
    tbl = tbl.explode('Grund')

    last_dates = tbl.groupby(group_cols, as_index = False)['Datum'].max()
    last_dates = last_dates.loc[last_dates['Grund'].isin(["Apfelmehltau", "Apfelschorf", "Ca-Düngung", "Bittersalz"])]

    return(last_dates)
    