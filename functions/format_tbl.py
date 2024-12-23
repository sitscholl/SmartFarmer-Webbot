def format_tbl(styler, tbl_perc, caption = None, rows_idx = None, t1 = 75, t2 = 100):

    styler.apply(
        lambda x: tbl_perc.map(
            lambda y: "color:darkorange;font-weight:bold;" if y > t1 else ""
        ),
        axis=None,
    )

    styler.apply(
        lambda x: tbl_perc.map(
            lambda y: "color:red;font-weight:bold;" if y > t2 else ""
        ),
        axis=None,
    )
    styler.set_table_styles([{'selector': 'th,td', 'props': [('border-style','solid')]}])
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

    if rows_idx is not None:
        #styler.set_properties(**{'background-color': '#ffffb3'}, subset=rows_idx)
        styler.apply(lambda x: ['background: yellow' if (x.name in rows_idx) else '' for i in x], axis=1)

    return styler
