# spint/processing/data_processor.py
from typing import Dict, Any, List
import pandas as pd
import numpy as np
import datetime
import logging
from ..config import ProcessingError

logger = logging.getLogger(__name__)

# Constants
RELEVANT_GRUND = [
    "Apfelmehltau",
    "Apfelschorf",
    "Blattdüngung",
    "Ca-Düngung",
    "Bittersalz"
]

REQUIRED_COLUMNS = {
    'smartfarmer': ['Datum', 'Mittel', 'Grund', 'Wiese', 'Sorte'],
    'grouping': ['Wiese', 'Sorte', 'Mittel', 'Grund']
}

MITTEL_GRUND_MAPPING = {
    "yaravita stopit": "Ca-Düngung",
    "epso combitop": "Bittersalz",
    "epso top": "Bittersalz",
    "ats": "Chemisches Ausdünnen",
    "supreme n": "Chemisches Ausdünnen"
}

class DataProcessor:
    """Processes SmartFarmer and SBR data to generate the final report dataset.
    
    This class handles the processing of agricultural data, including data reformatting,
    calculation of application dates, and threshold management.
    """

    def __init__(self, config: Dict[str, Any], static_data: Dict[str, pd.DataFrame]) -> None:
        """Initialize the DataProcessor.
        
        Args:
            config: Configuration dictionary containing processing parameters
            static_data: Dictionary containing static reference data frames
        """
        self.config = config
        self.static_data = static_data
        self.current_time = datetime.datetime.now(datetime.timezone.utc).astimezone()  # Timezone aware

    def _reformat_smartfarmer(self, sm_df: pd.DataFrame) -> pd.DataFrame:
        """Initial reformatting of the raw SmartFarmer DataFrame.
        
        Performs several transformations on the input data:
        1. Converts dates to timezone-aware datetime
        2. Normalizes 'Grund' values based on 'Mittel'
        3. Processes 'Anlage' field to extract 'Wiese' and 'Sorte'
        4. Splits and filters 'Grund' values
        
        Args:
            sm_df: Raw SmartFarmer DataFrame
            
        Returns:
            Reformatted DataFrame with standardized columns
            
        Raises:
            ProcessingError: If critical data processing steps fail
        """
        logger.info("Reformatting SmartFarmer data...")
        if sm_df.empty:
            logger.warning("SmartFarmer DataFrame is empty. Skipping reformatting.")
            return sm_df

        df = sm_df.copy()
        try:
            # Date Conversion
            df['Datum'] = pd.to_datetime(df['Datum'], format="%d/%m/%Y", errors='coerce')
            df['Datum'] = df['Datum'].dt.tz_localize(self.config['general']['timezone'])

            if df['Datum'].isnull().any():
                logger.warning("Some 'Datum' values in SmartFarmer data failed conversion or were missing.")
                df.dropna(subset=['Datum'], inplace=True)

            # Normalize 'Grund' based on 'Mittel'
            if 'Mittel' in df.columns:
                df['Mittel'] = df['Mittel'].astype(str)
                mittel_lower = df['Mittel'].str.lower()
                if 'Grund' not in df.columns:
                    df['Grund'] = ''
                df['Grund'] = df['Grund'].astype(str)

                # Apply mappings from constant
                for mittel, grund in MITTEL_GRUND_MAPPING.items():
                    df['Grund'] = np.where(mittel_lower == mittel, grund, df['Grund'])
            else:
                logger.warning("'Mittel' column not found in SmartFarmer data. Cannot normalize 'Grund'.")


            # Adjust 'Anlage' names and extract 'Wiese' and 'Sorte'
            if 'Anlage' in df.columns:
                df['Anlage'] = df['Anlage'].astype(str)
                df['Anlage'] = df['Anlage'].str.replace('Neuacker Klein', 'Neuacker', regex=False)
                # Extract Wiese (first word)
                df['Wiese'] = df['Anlage'].str.split(n=1).str[0]
                # Extract Sorte (text between first space and last year-like number) - Improved Regex
                # Looks for Space + Text + Space + 4 digits + End of string OR Space
                df['Sorte'] = df['Anlage'].str.extract(r'\s(.+?)\s*(?:\b[12]\d{3}\b|$)', expand=False).str.strip()

                # Handle cases where extraction might fail
                df['Wiese'] = df['Wiese'].fillna('Unbekannt')
                df['Sorte'] = df['Sorte'].fillna('Unbekannt')
            else:
                logger.warning("'Anlage' column not found. Cannot extract 'Wiese' and 'Sorte'.")
                df['Wiese'] = 'Unbekannt'
                df['Sorte'] = 'Unbekannt'


            # Split and explode 'Grund' field
            if 'Grund' in df.columns:
                df['Grund'] = df['Grund'].str.split(',\s*')  # Split by comma and optional spaces
                df = df.explode('Grund')
                df['Grund'] = df['Grund'].str.strip()  # Clean up whitespace
                # Filter for relevant Grund values after exploding
                df = df[df['Grund'].isin(RELEVANT_GRUND)]
            else:
                logger.warning("'Grund' column not available for exploding.")

            logger.info("SmartFarmer data reformatting complete.")
            # Select and return relevant columns
            available_cols = [col for col in REQUIRED_COLUMNS['smartfarmer'] if col in df.columns]
            return df[available_cols]

        except pd.errors.OutOfBoundsDatetime as e:
            logger.error(f"Invalid date format in SmartFarmer data: {e}", exc_info=True)
            raise ProcessingError(f"Invalid date format in SmartFarmer data: {e}") from e
        except ValueError as e:
            logger.error(f"Value error while processing SmartFarmer data: {e}", exc_info=True)
            raise ProcessingError(f"Value error in SmartFarmer data: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error reformatting SmartFarmer data: {e}", exc_info=True)
            raise ProcessingError(f"Failed to reformat SmartFarmer data: {e}") from e


    def _calculate_last_dates(self, sm_df_reformatted: pd.DataFrame) -> pd.DataFrame:
        """Calculates the last application date for each Wiese/Sorte/Grund/Mittel combination.
        
        Args:
            sm_df_reformatted: Reformatted SmartFarmer DataFrame
            
        Returns:
            DataFrame with last application dates and days passed
            
        Raises:
            ProcessingError: If required columns are missing
        """
        logger.info("Calculating last application dates...")
        if sm_df_reformatted.empty:
            logger.warning("Reformatted SmartFarmer data is empty. Cannot calculate last dates.")
            return pd.DataFrame()  # Return empty df with expected columns later

        # Verify required columns are present
        group_cols = REQUIRED_COLUMNS['grouping']
        missing = [col for col in group_cols if col not in sm_df_reformatted.columns]
        if missing:
            raise ProcessingError(f"Cannot group SmartFarmer data, missing columns: {missing}")

        last_dates = sm_df_reformatted.groupby(group_cols, as_index=False)['Datum'].max()
        last_dates['Tage'] = (self.current_time - last_dates['Datum']).dt.days

        logger.info("Calculated last dates and days passed.")
        return last_dates

    def _add_thresholds_and_defaults(self, last_dates_df):
        """Merges static threshold data (rain, interval) and applies defaults."""
        logger.info("Adding thresholds and applying defaults...")
        if last_dates_df.empty:
            logger.warning("Last dates DataFrame is empty. Skipping threshold addition.")
            # Add expected columns for consistency downstream
            last_dates_df['Regenbestaendigkeit_min'] = np.nan
            last_dates_df['Regenbestaendigkeit_max'] = np.nan
            last_dates_df['Behandlungsintervall_min'] = np.nan
            last_dates_df['Behandlungsintervall_max'] = np.nan
            return last_dates_df

        df = last_dates_df.copy()

        # --- Regenbeständigkeit ---
        regen_data = self.static_data['regen']
        if not regen_data.empty:
             # Ensure 'Mittel' exists for merging
             if 'Mittel' not in df.columns: df['Mittel'] = 'Unbekannt'
             if 'Mittel' not in regen_data.columns:
                 logger.error("Static 'regen' data missing 'Mittel' column.")
             else:
                df = pd.merge(df, regen_data, on='Mittel', how='left')

                # Log missing Mittel in regen data
                missing_regen_mittel = df.loc[df['Regenbestaendigkeit_max'].isna(), 'Mittel'].unique()
                if len(missing_regen_mittel) > 0:
                    mittel_join = "\n\t- ".join(np.sort(missing_regen_mittel))
                    logger.warning(f"Regenbeständigkeit missing for {len(missing_regen_mittel)} Mittel. Applying default ({self.config['default_mm']}mm):\n\t- {mittel_join}")

                # Apply defaults
                df['Regenbestaendigkeit_max'] = df['Regenbestaendigkeit_max'].fillna(self.config['default_mm'])
                # Recalculate min based on potentially filled max
                df['Regenbestaendigkeit_min'] = df['Regenbestaendigkeit_min'].fillna(
                    (df['Regenbestaendigkeit_max'] * self.config['t1_factor']).round(1)
                )
        else:
            logger.warning("Static Regenbeständigkeit data is empty. Applying defaults to all.")
            df['Regenbestaendigkeit_max'] = self.config['default_mm']
            df['Regenbestaendigkeit_min'] = (df['Regenbestaendigkeit_max'] * self.config['t1_factor']).round(1)


        # --- Behandlungsintervall ---
        intervall_data = self.static_data['intervall']
        if not intervall_data.empty:
            merge_cols_intervall = ['Mittel', 'Sorte']
             # Ensure merge columns exist
            if not all(col in df.columns for col in merge_cols_intervall):
                missing = [col for col in merge_cols_intervall if col not in df.columns]
                logger.error(f"Cannot merge Behandlungsintervall, missing columns in main df: {missing}")
            elif not all(col in intervall_data.columns for col in merge_cols_intervall):
                 missing = [col for col in merge_cols_intervall if col not in intervall_data.columns]
                 logger.error(f"Static 'intervall' data missing columns: {missing}")
            else:
                df = pd.merge(df, intervall_data, on=merge_cols_intervall, how='left')

                # Log missing Mittel/Sorte combinations in intervall data
                missing_intervall_combos = df.loc[df['Behandlungsintervall_max'].isna(), ['Mittel', 'Sorte']].drop_duplicates()
                if not missing_intervall_combos.empty:
                    combo_strings = [f"{row['Mittel']} / {row['Sorte']}" for _, row in missing_intervall_combos.iterrows()]
                    mittel_join = "\n\t- ".join(sorted(combo_strings))
                    logger.warning(f"Behandlungsintervall missing for {len(missing_intervall_combos)} Mittel/Sorte combinations. Applying default ({self.config['default_days']} days):\n\t- {mittel_join}")

                # Apply defaults
                df['Behandlungsintervall_max'] = df['Behandlungsintervall_max'].fillna(self.config['default_days'])
                # Recalculate min based on potentially filled max
                df['Behandlungsintervall_min'] = df['Behandlungsintervall_min'].fillna(
                     # Round T1 for days to integer
                    (df['Behandlungsintervall_max'] * self.config['t1_factor']).round(0)
                )
        else:
            logger.warning("Static Behandlungsintervall data is empty. Applying defaults to all.")
            df['Behandlungsintervall_max'] = self.config['default_days']
            df['Behandlungsintervall_min'] = (df['Behandlungsintervall_max'] * self.config['t1_factor']).round(0)

        # Convert threshold columns to appropriate types (e.g., float or int)
        num_cols = ['Regenbestaendigkeit_min', 'Regenbestaendigkeit_max', 'Behandlungsintervall_min', 'Behandlungsintervall_max', 'Tage']
        for col in num_cols:
            if col in df.columns:
                 # Use Int64 for integer columns to handle potential NaNs before fillna
                 if 'intervall' in col or 'Tage' in col:
                     df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                 else: # Regen can be float
                    df[col] = pd.to_numeric(df[col], errors='coerce')


        logger.info("Thresholds added and defaults applied.")
        return df

    def _select_dominant_treatment(self, df_with_thresholds):
        """If multiple treatments for the same Wiese/Sorte/Grund occur on the same day,
           select the one likely offering longest protection based on thresholds."""
        logger.info("Selecting dominant treatment for same-day applications...")
        if df_with_thresholds.empty:
            return df_with_thresholds

        # Sort by date (desc), then by thresholds (desc) to prioritize longer-lasting treatments
        # Handle potential NaNs in sorting columns by filling temporarily or ensuring numeric types
        sort_cols = ["Datum", "Regenbestaendigkeit_max", "Behandlungsintervall_max"]
        df = df_with_thresholds.sort_values(by=sort_cols, ascending=False, na_position='first') # Put NaNs first so they are dropped if non-NaN exists

        # Drop duplicates, keeping the first entry (which is the "best" based on sorting)
        # Group by Wiese, Sorte, Grund to find the last relevant treatment for that purpose
        keep_cols = ['Wiese', 'Sorte', 'Grund']
        df_final = df.drop_duplicates(subset=keep_cols, keep='first')

        logger.info("Dominant treatments selected.")
        return df_final


    def _calculate_rainfall(self, treatments_df, sbr_df):
        """Calculates cumulative rainfall since each treatment."""
        logger.info("Calculating cumulative rainfall...")
        if treatments_df.empty:
            logger.warning("Treatments DataFrame is empty. Skipping rainfall calculation.")
            treatments_df['Niederschlag'] = np.nan
            return treatments_df
        if sbr_df is None or sbr_df.empty:
            logger.warning("SBR weather data is not available or empty. Rainfall cannot be calculated.")
            treatments_df['Niederschlag'] = np.nan
            return treatments_df

        # Ensure SBR data has necessary columns and correct types
        if 'Datum' not in sbr_df.columns or 'Nied.' not in sbr_df.columns:
             logger.error("SBR data missing 'Datum' or 'Nied.' column for rainfall calculation.")
             treatments_df['Niederschlag'] = np.nan
             return treatments_df
        if not pd.api.types.is_datetime64_any_dtype(sbr_df['Datum']):
             sbr_df['Datum'] = pd.to_datetime(sbr_df['Datum'], errors='coerce')
             logger.warning("Converted SBR 'Datum' column type.")
        if not pd.api.types.is_numeric_dtype(sbr_df['Nied.']):
            sbr_df['Nied.'] = pd.to_numeric(sbr_df['Nied.'], errors='coerce')
            logger.warning("Converted SBR 'Nied.' column type.")

        # Make SBR datetime timezone aware to match treatments_df['Datum'] and current_time
        if sbr_df['Datum'].dt.tz is None:
            logger.debug("Making SBR Datum timezone-aware.")
            sbr_df['Datum'] = sbr_df['Datum'].dt.tz_localize(self.config['general']['timezone'], ambiguous='infer')


        # Prepare for merging/lookup: Sort SBR data by time
        sbr_sorted = sbr_df.sort_values('Datum').set_index('Datum')

        unique_start_dates = treatments_df['Datum'].unique()

        # Calculate sums efficiently
        rainfall_sums = {}
        for start_date in unique_start_dates:
            # Ensure start_date is timezone aware for comparison
            if start_date.tzinfo is None:
                 start_date = start_date.tz_localize(self.config['general']['timezone']) # Or infer from treatments_df

            # Select relevant period from SBR data (inclusive start, exclusive end)
            # Add a small epsilon to start_date for > comparison if needed,
            # but >= start and < now should work.
            relevant_rain = sbr_sorted[(sbr_sorted.index >= start_date) & (sbr_sorted.index < self.current_time)]
            # Sum the 'niederschl' column, handle NaNs
            total_rain = relevant_rain['Nied.'].sum(skipna=True)
            rainfall_sums[start_date] = round(total_rain, 1) # Round to one decimal

        # Map the calculated sums back to the treatments DataFrame
        treatments_df['Niederschlag'] = treatments_df['Datum'].map(rainfall_sums)

        # Fill NaN for any dates where calculation might have failed (e.g., no SBR data for that period)
        treatments_df['Niederschlag'] = treatments_df['Niederschlag'].fillna(np.nan) # Keep as NaN to indicate missing data

        logger.info("Rainfall calculation complete.")
        return treatments_df

    def process(self, smartfarmer_raw_df, sbr_raw_df=None):
        """Executes the full data processing pipeline."""
        logger.info("Starting data processing pipeline...")
        try:
            sm_reformatted = self._reformat_smartfarmer(smartfarmer_raw_df)
            if sm_reformatted.empty:
                logger.warning("SmartFarmer data is empty after reformatting. Cannot proceed.")
                return pd.DataFrame() # Return empty DataFrame

            last_dates = self._calculate_last_dates(sm_reformatted)
            if last_dates.empty:
                 logger.warning("No last dates calculated. Cannot proceed.")
                 return pd.DataFrame()

            with_thresholds = self._add_thresholds_and_defaults(last_dates)
            dominant_treatments = self._select_dominant_treatment(with_thresholds)
            final_data = self._calculate_rainfall(dominant_treatments, sbr_raw_df)

            # Final cleanup/ordering
            final_data = final_data.sort_values(['Wiese', 'Sorte', 'Grund'])
            logger.info("Data processing pipeline finished successfully.")

            # Define final columns order (adjust as needed)
            ordered_output_cols = [
                 'Wiese', 'Sorte', 'Grund', 'Datum', 'Mittel',
                 'Tage', 'Behandlungsintervall_min', 'Behandlungsintervall_max',
                 'Niederschlag', 'Regenbestaendigkeit_min', 'Regenbestaendigkeit_max'
            ]
            # Return only existing columns in the defined order
            final_data = final_data[[col for col in ordered_output_cols if col in final_data.columns]]

            return final_data

        except (ProcessingError, Exception) as e:
            logger.error(f"Data processing pipeline failed: {e}", exc_info=True)
            raise ProcessingError(f"Data processing failed: {e}") from e