import numpy as np
import pandas as pd

def format_tbl(tbl_string, vals, t1, t2, caption = None):

    colormat = np.where(vals >= t2,
                        'background-color: red',
                        np.where(vals >= t1, 
                            'background-color: orange', ''))

    styler = tbl_string.style.apply(lambda _: colormat, axis=None)

    styler.set_table_styles([{'selector': 'th,td', 'props': [('border','1px solid')]}])
    if caption is not None:
        styler.set_caption(caption).set_table_styles(
            [
                {
                    "selector": "caption",
                    "props": "caption-side: bottom;",
                }
            ],
            overwrite=False,
        )
    return styler
