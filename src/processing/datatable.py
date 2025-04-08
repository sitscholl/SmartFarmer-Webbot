import pandas as pd
import numpy as np

class DataTable:

    colnames_mapping =  {
        "Regenbestaendigkeit": "Niederschlag",
        "Behandlungsintervall": "Tage"
    }

    def __init__(self, data: pd.DataFrame, val_cols: list[str], columns: list[str], index: list[str]):

        self.data = data
        self.val_cols = val_cols
        self.columns = columns
        self.index = index

    def get_data(self):
        return self.data

    def get_values(self):
        return self.val_cols

    def get_columns(self):
        return self.columns

    def get_index(self):
        return self.index

    def get_amounts(self):
        return self.data.pivot(
                columns=self.columns, index=self.index, values=self.val_cols
            ).round(1)

    def get_thresholds(self, type: str):
        if type == 'max':
            return self.data.pivot(
                columns=self.columns,
                index=self.index,
                values=[
                    f"{i}_{type}"
                    for i in self.colnames_mapping.keys()
                    if f"{i}_{type}" in self.data.columns
                ],
            ).rename(
                columns={
                    f"{i}_{type}": self.colnames_mapping[i.rstrip(f"_{type}")]
                    for i in self.colnames_mapping.keys()
                },
                level=0,
            )[self.val_cols].astype(int)

        elif type == "min":
            return self.data.pivot(
                columns=self.columns,
                index=self.index,
                values=[
                    f"{i}_{type}"
                    for i in self.colnames_mapping.keys()
                    if f"{i}_{type}" in self.data.columns
                ],
            ).rename(
                columns={
                    f"{i}_{type}": self.colnames_mapping[i.rstrip(f"_{type}")]
                    for i in self.colnames_mapping.keys()
                },
                level=0,
            )[self.val_cols].astype(int)
        else:
            raise ValueError(f"Threshold type {type} not supported. Use 'min' or 'max'.")

    def get_mittel_name(self, mittel_col = 'Mittel'):
        return self.data.pivot(
                columns=self.columns, index=self.index, values=mittel_col
            )

    def get_perc_passed(self):
        return (
            ((self.get_amounts() / self.get_thresholds(type="max")) * 100)
            .round(0)
        )

    def get_string_data(self):
        return (
            self.get_amounts().astype(str).replace('nan', '')
            + "/"
            + self.get_thresholds(type="max").astype(str)
            + " ("
            + self.get_mittel_name()
            + ")"
        )

    def style_tbl(self, param: str, caption: str = None):

        vals = self.get_amounts()[param]
        t1 = self.get_thresholds(type = 'min')[param]
        t2 = self.get_thresholds(type = 'max')[param]

        colormat = np.where((vals >= t2).fillna(False),
                            'background-color: red',
                            np.where((vals >= t1).fillna(False), 
                                'background-color: orange', ''))

        styler = self.get_string_data()[param].style.apply(lambda _: colormat, axis=None)

        headers = {
                "selector": "th",
                "props": "border:1px solid #707B7C;border-collapse:collapse;padding:5px"
            }
        cells = {
                "selector": "td",
                "props": "border:1px solid #707B7C;border-collapse:collapse;padding:5px"
            }  
        full = {
            "selector": "",
            "props": [("border-collapse", "collapse"), ("border", "1px solid #707B7C")],
        }

        styler.set_table_styles([headers,cells,full])

        return styler
