# spint/reporting/reporter.py
import pandas as pd
import numpy as np
from jinja2 import Environment, FileSystemLoader
import smtplib
from email.message import EmailMessage
import logging
import datetime
from pytz import timezone
from ..config import ReportError

logger = logging.getLogger(__name__)

class Reporter:
    """Generates and sends the treatment overview report."""

    def __init__(self, config):
        self.config = config
        self.template_path = config['template_path']
        self.email_recipients = config['email_recipients']
        self.gm_user = config['gm_user']
        self.gm_pwd = config['gm_pwd']

        if not self.template_path.exists():
            raise ReportError(f"Template directory not found: {self.template_path}")
        self.env = Environment(loader=FileSystemLoader(self.template_path), autoescape=True)


    def _prepare_pivot_data(self, processed_df):
        """Pivots the data for the report structure and creates display strings."""
        logger.debug("Pivoting data for report...")
        if processed_df.empty:
            logger.warning("Processed data is empty, cannot create pivot tables.")
            return {} # Return empty dict

        # Columns to pivot on values
        value_cols = []
        if 'Tage' in processed_df.columns: value_cols.append('Tage')
        if 'Niederschlag' in processed_df.columns: value_cols.append('Niederschlag')

        threshold_cols_map = {
            'Tage': ('Behandlungsintervall_min', 'Behandlungsintervall_max'),
            'Niederschlag': ('Regenbestaendigkeit_min', 'Regenbestaendigkeit_max')
        }
        mittel_col = 'Mittel'
        index_cols = ['Wiese', 'Sorte']
        column_col = 'Grund' # The reason/purpose of treatment

        pivot_tables = {}

        if not value_cols:
            logger.warning("No value columns ('Tage', 'Niederschlag') found in processed data for pivoting.")
            return {}

        # Ensure index and column cols exist
        if not all(col in processed_df.columns for col in index_cols + [column_col]):
             missing = [col for col in index_cols + [column_col] if col not in processed_df.columns]
             logger.error(f"Cannot pivot data, missing required columns: {missing}")
             return {}

        # Iterate through each value type (Tage, Niederschlag) to create separate tables
        for val_col in value_cols:
            logger.debug(f"Pivoting for: {val_col}")
            min_thresh_col, max_thresh_col = threshold_cols_map[val_col]

            # Check if necessary columns exist for this pivot value
            required_pivot_cols = [val_col, min_thresh_col, max_thresh_col, mittel_col]
            if not all(c in processed_df.columns for c in required_pivot_cols):
                missing_p = [c for c in required_pivot_cols if c not in processed_df.columns]
                logger.warning(f"Skipping pivot for '{val_col}', missing columns: {missing_p}")
                continue

            try:
                # Pivot current value, thresholds, and Mittel name
                pivot_val = processed_df.pivot_table(index=index_cols, columns=column_col, values=val_col, aggfunc='first')
                pivot_t1 = processed_df.pivot_table(index=index_cols, columns=column_col, values=min_thresh_col, aggfunc='first')
                pivot_t2 = processed_df.pivot_table(index=index_cols, columns=column_col, values=max_thresh_col, aggfunc='first')
                pivot_mittel = processed_df.pivot_table(index=index_cols, columns=column_col, values=mittel_col, aggfunc='first') # Assumes one mittel per group after processing

                # Combine into a display string table: "Value / T2 (Mittel)"
                # Format numbers appropriately (e.g., Tage as int, Niederschlag as float)
                if val_col == 'Tage':
                    str_format = lambda v: f"{v:.0f}" if pd.notna(v) else ""
                    t2_format = lambda v: f"{v:.0f}" if pd.notna(v) else "?"
                else: # Niederschlag
                    str_format = lambda v: f"{v:.1f}" if pd.notna(v) else ""
                    t2_format = lambda v: f"{v:.1f}" if pd.notna(v) else "?"

                # Vectorized string creation
                display_str_df = (
                     pivot_val.applymap(str_format) +
                     " / " +
                     pivot_t2.applymap(t2_format) +
                     " (" +
                     pivot_mittel.fillna("?") + # Show '?' if mittel is missing
                     ")"
                )
                 # Replace " / ? (?)" or similar artifacts from missing data with empty string
                display_str_df = display_str_df.replace(r'^ / \? \(\?\)$', '', regex=True) # Handle fully missing rows
                display_str_df = display_str_df.replace(r' / \? ', ' / ? ', regex=False) # Handle missing threshold
                display_str_df = display_str_df.replace(r' \(\?\) ', '', regex=False) # Handle missing mittel name

                # Store necessary data for styling
                pivot_tables[val_col] = {
                    'display': display_str_df,
                    'values': pivot_val,
                    't1': pivot_t1,
                    't2': pivot_t2
                }
            except Exception as e:
                logger.error(f"Error pivoting data for '{val_col}': {e}", exc_info=True)
                # Continue to next pivot table type if possible

        return pivot_tables


    def _style_table(self, display_df, values_df, t1_df, t2_df):
        """Applies conditional background styling to the display DataFrame."""
        logger.debug("Applying styling to table...")

        # Create a DataFrame for background colors based on thresholds
        # Ensure indices/columns match the display_df
        color_df = pd.DataFrame('', index=display_df.index, columns=display_df.columns)

        # Align threshold dataframes to the display dataframe's structure
        t1_aligned = t1_df.reindex_like(display_df)
        t2_aligned = t2_df.reindex_like(display_df)
        values_aligned = values_df.reindex_like(display_df)


        # Conditions for styling (handle NaNs)
        # Ensure comparisons are between numeric types
        numeric_values = pd.to_numeric(values_aligned.stack(dropna=False), errors='coerce')
        numeric_t1 = pd.to_numeric(t1_aligned.stack(dropna=False), errors='coerce')
        numeric_t2 = pd.to_numeric(t2_aligned.stack(dropna=False), errors='coerce')


        is_ge_t2 = (numeric_values >= numeric_t2) & pd.notna(numeric_values) & pd.notna(numeric_t2)
        is_ge_t1 = (numeric_values >= numeric_t1) & (numeric_values < numeric_t2) & pd.notna(numeric_values) & pd.notna(numeric_t1) & pd.notna(numeric_t2) # Also check T2 notna
        is_ge_t1_no_t2 = (numeric_values >= numeric_t1) & pd.notna(numeric_values) & pd.notna(numeric_t1) & pd.isna(numeric_t2) # >= T1 when T2 is missing -> orange

        # Apply styles based on conditions back to the color_df shape
        color_df_flat = color_df.stack(dropna=False)
        color_df_flat[is_ge_t2] = 'background-color: #FF7F7F' # Lighter Red
        color_df_flat[is_ge_t1 | is_ge_t1_no_t2] = 'background-color: #FFD700' # Gold / Orangeish

        color_styler_df = color_df_flat.unstack()

        # Create the Styler object from the display DataFrame
        styler = display_df.style

        # Apply the calculated background colors
        styler.apply(lambda _: color_styler_df, axis=None)

        # Apply general table styles (borders, padding)
        styles = [
            {'selector': 'th', 'props': [('border', '1px solid #707B7C'), ('padding', '5px'), ('text-align', 'center'), ('background-color', '#f2f2f2')]},
            {'selector': 'td', 'props': [('border', '1px solid #707B7C'), ('padding', '5px'), ('text-align', 'center')]},
            {'selector': 'table', 'props': [('border-collapse', 'collapse'), ('border', '1px solid #707B7C'), ('width', 'auto'), ('margin', 'auto')]}, # Center table?
             {'selector': '.index_name', 'props': [('text-align', 'left'), ('font-weight', 'bold')]}, # Style index names
             {'selector': 'th.col_heading', 'props': [('text-align', 'center'), ('font-weight', 'bold')]}, # Style column headers
             {'selector': 'th.row_heading', 'props': [('text-align', 'left')]}, # Style row headers (index values)
        ]
        styler.set_table_styles(styles)

        # Add a caption maybe?
        # styler.set_caption("My Table Caption")

        # Format NaN values as empty strings in the final HTML
        styler.format(na_rep="")

        return styler


    def generate_html_report(self, processed_df):
        """Generates the full HTML report body using Jinja2."""
        logger.info("Generating HTML report...")
        if processed_df is None or processed_df.empty:
            logger.warning("No processed data available to generate report.")
            # Return a simple HTML message indicating no data
            return "<p>Keine Daten zur Berichterstellung verfügbar.</p>"

        pivot_data = self._prepare_pivot_data(processed_df)
        if not pivot_data:
             return "<p>Daten konnten nicht für den Bericht formatiert werden.</p>"


        styled_tables_html = {}
        for value_type, data in pivot_data.items():
            logger.debug(f"Styling table for {value_type}...")
            styler = self._style_table(data['display'], data['values'], data['t1'], data['t2'])
            # Include table classes for potential CSS targeting in the template
            styled_tables_html[value_type] = styler.to_html(classes=["dataframe", value_type.lower()]) # e.g., class="dataframe tage"

        # Render the Jinja2 template
        try:
            template = self.env.get_template("mail_template.html") # Ensure template name matches
            report_time = datetime.datetime.now(tz=timezone("Europe/Berlin"))
            html_body = template.render(
                report_date=report_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                tables_dict=styled_tables_html # Pass dict of HTML table strings
                # Add any other variables needed by the template here
            )
            logger.info("HTML report generated successfully.")
            return html_body
        except Exception as e:
            logger.error(f"Error rendering HTML template: {e}", exc_info=True)
            raise ReportError(f"Failed to render HTML report: {e}")


    def send_email(self, html_content):
        """Sends the generated HTML report via Gmail."""
        if not html_content:
            logger.warning("HTML content is empty, skipping email sending.")
            return

        if not self.gm_user or not self.gm_pwd:
             logger.error("Gmail credentials not configured. Cannot send email.")
             raise ReportError("Gmail credentials missing.")
        if not self.email_recipients:
            logger.warning("No email recipients configured. Skipping email sending.")
            return


        logger.info(f"Sending email report to: {', '.join(self.email_recipients)}")
        msg = EmailMessage()
        msg["Subject"] = f'Pflanzenschutz Übersicht - {datetime.date.today().strftime("%Y-%m-%d")}'
        msg['From'] = self.gm_user
        msg['To'] = ", ".join(self.email_recipients)
        msg.set_content("Bitte aktivieren Sie HTML, um diesen Bericht anzuzeigen.") # Fallback content
        msg.add_alternative(html_content, subtype="html")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
                smtp_server.login(self.gm_user, self.gm_pwd)
                smtp_server.send_message(msg)
            logger.info('Email report sent successfully!')
        except smtplib.SMTPAuthenticationError:
             logger.error("Gmail authentication failed. Check App Password and credentials.")
             raise ReportError("Gmail authentication failed.")
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            raise ReportError(f"Failed to send email: {e}") from e


    # --- Google Sheets Function (Optional, keep if needed) ---
    # def send_to_google_sheets(self, dataframe, spreadsheet_name, worksheet_name):
    #     """Sends a DataFrame to a Google Sheet."""
    #     # Requires gspread and gspread-dataframe
    #     # Ensure self.config['google_creds_path'] is set
    #     try:
    #         import gspread
    #         from gspread_dataframe import set_with_dataframe
    #     except ImportError:
    #         logger.error("gspread or gspread-dataframe not installed. Cannot send to Google Sheets.")
    #         raise ReportError("Missing Google Sheets libraries.")

    #     logger.info(f"Sending data to Google Sheet: {spreadsheet_name}/{worksheet_name}")
    #     creds_path = self.config.get('google_creds_path')
    #     if not creds_path or not Path(creds_path).exists():
    #          logger.error(f"Google Cloud credentials file not found at: {creds_path}")
    #          raise ReportError("Google Cloud credentials file missing.")

    #     try:
    #         scope = [
    #             "https://spreadsheets.google.com/feeds",
    #             "https://www.googleapis.com/auth/spreadsheets",
    #             "https://www.googleapis.com/auth/drive.file",
    #             "https://www.googleapis.com/auth/drive",
    #         ]
    #         client = gspread.service_account(filename=creds_path, scopes=scope)
    #         gtable = client.open(spreadsheet_name)
    #         try:
    #             worksheet = gtable.worksheet(worksheet_name)
    #         except gspread.WorksheetNotFound:
    #              logger.info(f"Worksheet '{worksheet_name}' not found, creating it.")
    #              # Decide on size or let it resize automatically
    #              worksheet = gtable.add_worksheet(title=worksheet_name, rows="1", cols="1") # Start small

    #         # Clear sheet before writing? Optional. worksheet.clear()
    #         set_with_dataframe(worksheet=worksheet, dataframe=dataframe, include_index=True, include_column_header=True, resize=True)
    #         logger.info('Data sent to Google Sheets successfully!')

    #     except gspread.exceptions.APIError as e:
    #          logger.error(f"Google Sheets API error: {e}", exc_info=True)
    #          raise ReportError(f"Google Sheets API error: {e}")
    #     except Exception as e:
    #         logger.error(f"Failed to send data to Google Sheets: {e}", exc_info=True)
    #         raise ReportError(f"Failed to send data to Google Sheets: {e}") from e