import pandas as pd
import datetime

def load_regenbestaendigkeit(p, t1_factor):
    tbl_regenbestaendigkeit = pd.read_csv(
        p, encoding="latin-1"
    ).rename(columns={"Regenbestaendigkeit": "Regenbestaendigkeit_max"})
    tbl_regenbestaendigkeit["Regenbestaendigkeit_min"] = (
        tbl_regenbestaendigkeit["Regenbestaendigkeit_max"] * t1_factor
    )
    return tbl_regenbestaendigkeit

def load_sortenanfaelligkeit(p):
    tbl_anfaelligkeit = pd.read_csv(p, encoding="latin-1")
    return(tbl_anfaelligkeit)

def load_behandlungsintervall(p, sortenanfaelligkeit, season = 'Vorblüte' if datetime.datetime.now().month <= 6 else 'Sommer'):
    tbl_behandlungsintervall = pd.read_csv(
        p, encoding="latin-1", sep="\t"
    )
    tbl_behandlungsintervall = tbl_behandlungsintervall.loc[
        (tbl_behandlungsintervall["Mittel"] != "Nimrod 250 EW")
        | (tbl_behandlungsintervall["Jahreszeit"] == season)
    ]

    tbl_behandlungsintervall_re = (
        tbl_behandlungsintervall
        .melt(
            id_vars=["Mittel", "Jahreszeit", "Range"],
            var_name="Mehltauanfälligkeit",
            value_name="Behandlungsintervall",
        )
        .merge(sortenanfaelligkeit, on = "Mehltauanfälligkeit")
        .pivot(columns = 'Range', values = 'Behandlungsintervall', index = ['Mittel', 'Sorte'])
        .reset_index()
        .rename(columns = {'min': 'Behandlungsintervall_min', 'max': 'Behandlungsintervall_max'})
    )[['Mittel', 'Sorte', 'Behandlungsintervall_min', 'Behandlungsintervall_max']]

    return tbl_behandlungsintervall_re
