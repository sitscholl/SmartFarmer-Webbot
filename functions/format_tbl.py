import numpy as np
import pandas as pd

def format_tbl(tbl_string, vals, t1, t2, caption = None):

    colormat = np.where(vals >= t2,
                        'background-color: red',
                        np.where(vals >= t1, 
                            'background-color: orange', ''))

    styler = tbl_string.style.apply(lambda _: colormat, axis=None)

    headers = {
    "selector": "th",
    "props": "border:1px solid #707B7C;border-collapse:collapse;padding:5px"
    }
    cells = {
    "selector": "td",
    "props": "border:1px solid #707B7C;border-collapse:collapse;padding:5px"
    }  
    full = {"selector": "", "props": [("border-collapse", "collapse"), ("border", "1px solid #707B7C")]}

    styler.set_table_styles([headers,cells,full])

    return styler
