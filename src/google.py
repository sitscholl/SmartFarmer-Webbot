from email.message import EmailMessage
import smtplib
import gspread
from gspread_dataframe import set_with_dataframe
import logging

logger = logging.getLogger(__name__)

def send_mail(
    content: str,
    username: str,
    password: str,
    recipients: list[str],
    subject: str = 'Pflanzenschutz Übersicht',
    fromaddr: str = 'tscholl.simon@gmail.com',
    port = 465,
    host = 'smtp.gmail.com'):

    msg = EmailMessage()

    msg["Subject"] = subject
    msg['From'] = fromaddr
    msg['To'] = recipients

    msg.set_content(content, subtype="html")

    with smtplib.SMTP_SSL(host, port) as smtp_server:
        smtp_server.login(username, password)
        smtp_server.send_message(msg)

    logger.info('Email versendet!')

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