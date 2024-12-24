from pytz import timezone
from email.message import EmailMessage
import smtplib
import datetime
import numpy as np
import os
import gspread
from gspread_dataframe import set_with_dataframe

from functions.format_tbl import format_tbl

def send_mail(tbl_string, tbl_perc, user, pwd, recipients = 'tscholl.simon@gmail.com'):

    msg = EmailMessage()
    msg["Subject"] = 'Pflanzenschutz Übersicht'
    msg['From'] = 'tscholl.simon@gmail.com'
    msg['To'] = recipients# 'tscholl.simon@gmail.com, erlhof.latsch@gmail.com'

    params = np.unique(tbl_string.columns.get_level_values(0))
    msg.set_content(
        "".join(
            [
                f"""\
            <h2>{param}</h2>
            {tbl_string[param].style.pipe(
                            format_tbl,
                            tbl_perc=tbl_perc['Tage'],
                            caption=f"Letzte Aktualisierung: {datetime.datetime.now(tz = timezone('Europe/Berlin')):%Y-%m-%d %H:%M}",
                        ).to_html()}

        """
                for param in params
            ]
        ),
        subtype="html",
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
        smtp_server.login(user, pwd)
        smtp_server.send_message(msg)

    print('Email versendet!')

def send_sheets(tbl_string, creds = 'gcloud_key.json', spreadsheet = 'Behandlungsübersicht', worksheet = 'Behandlungsübersicht'):

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]

    client = gspread.service_account(filename = creds, scopes = scope)
    gtable = client.open(spreadsheet)
    ws = gtable.worksheet(worksheet)

    set_with_dataframe(worksheet=ws, dataframe=tbl_string, include_index=True, include_column_header=True, resize=True)
    print('Tabelle an Google Sheets gesendet!')