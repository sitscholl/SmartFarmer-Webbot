# spint/data_loaders/static_data.py
import pandas as pd
import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class StaticDataLoader:
    """Loads static data files needed for processing."""

    def __init__(self, data_path: Path, t1_factor: float):
        self.data_path = data_path
        self.t1_factor = t1_factor
        if not self.data_path.is_dir():
             raise FileNotFoundError(f"Static data directory not found: {self.data_path}")

    def load_regenbestaendigkeit(self):
        """Loads and prepares rainfall resistance data."""
        file_path = self.data_path / "regenbestaendigkeit.csv"
        logger.debug(f"Loading Regenbestaendigkeit from: {file_path}")
        try:
            df = pd.read_csv(file_path, encoding="latin-1")
            # Rename directly to standard names
            df = df.rename(columns={"Regenbestaendigkeit": "Regenbestaendigkeit_max"})
            if "Regenbestaendigkeit_max" not in df.columns:
                raise ValueError("Column 'Regenbestaendigkeit' not found in regenbestaendigkeit.csv")

            # Calculate min threshold
            df["Regenbestaendigkeit_min"] = (df["Regenbestaendigkeit_max"] * self.t1_factor).round(1) # Allow decimals maybe?
            logger.info(f"Loaded Regenbestaendigkeit data. Shape: {df.shape}")
            return df[['Mittel', 'Regenbestaendigkeit_min', 'Regenbestaendigkeit_max']] # Select needed columns
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading Regenbestaendigkeit data: {e}", exc_info=True)
            raise ProcessingError(f"Failed to load {file_path}: {e}") from e


    def load_sortenanfaelligkeit(self):
        """Loads variety susceptibility data."""
        file_path = self.data_path / "sortenanfaelligkeit.csv"
        logger.debug(f"Loading Sortenanfälligkeit from: {file_path}")
        try:
            df = pd.read_csv(file_path, encoding="latin-1")
            logger.info(f"Loaded Sortenanfälligkeit data. Shape: {df.shape}")
             # Basic validation
            if not {'Sorte', 'Mehltauanfälligkeit'}.issubset(df.columns):
                 raise ValueError("sortenanfaelligkeit.csv missing required columns 'Sorte' or 'Mehltauanfälligkeit'")
            return df
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading Sortenanfälligkeit data: {e}", exc_info=True)
            raise ProcessingError(f"Failed to load {file_path}: {e}") from e

    def load_behandlungsintervall(self, sortenanfaelligkeit_df):
        """Loads and prepares treatment interval data, merging with susceptibility."""
        file_path = self.data_path / "behandlungsintervall.csv"
        logger.debug(f"Loading Behandlungsintervall from: {file_path}")
        try:
            df = pd.read_csv(file_path, encoding="latin-1", sep="\t") # Assuming tab separated based on load.py
            logger.info(f"Loaded Behandlungsintervall data. Shape: {df.shape}")

             # Filter based on season (determine season once)
            current_month = datetime.datetime.now().month
            # Adjust logic if needed (e.g., <= 5 for Vorblüte)
            season = 'Vorblüte' if current_month <= 6 else 'Sommer'
            logger.info(f"Filtering Behandlungsintervall for season: {season}")

            # Apply filtering (Nimrod example)
            df_filtered = df[
                (df["Mittel"] != "Nimrod 250 EW") | (df["Jahreszeit"] == season)
            ].copy() # Use copy to avoid SettingWithCopyWarning

            if df_filtered.empty:
                logger.warning("Behandlungsintervall dataframe is empty after filtering.")
                # Return an empty DataFrame with expected columns to avoid downstream errors
                return pd.DataFrame(columns=['Mittel', 'Sorte', 'Behandlungsintervall_min', 'Behandlungsintervall_max'])


            # Validate required columns before melt
            required_melt_cols = ["Mittel", "Jahreszeit", "Range"]
            if not all(col in df_filtered.columns for col in required_melt_cols):
                raise ValueError(f"behandlungsintervall.csv missing required columns for melting: {required_melt_cols}")


            # Melt and merge
            id_vars = ["Mittel", "Jahreszeit", "Range"]
            value_vars = [col for col in df_filtered.columns if col not in id_vars] # Dynamically get susceptibility level columns
            if not value_vars:
                 raise ValueError("No susceptibility level columns found to melt in behandlungsintervall.csv")

            df_melted = df_filtered.melt(
                id_vars=id_vars,
                value_vars=value_vars, # Use dynamic columns
                var_name="Mehltauanfälligkeit",
                value_name="Behandlungsintervall",
            )

            # Merge with susceptibility data
            if sortenanfaelligkeit_df.empty:
                 logger.warning("Sortenanfälligkeit data is empty, cannot merge with Behandlungsintervall.")
                 # Return empty or partially processed data? Returning empty for safety.
                 return pd.DataFrame(columns=['Mittel', 'Sorte', 'Behandlungsintervall_min', 'Behandlungsintervall_max'])

            # Ensure merge keys exist
            if "Mehltauanfälligkeit" not in sortenanfaelligkeit_df.columns:
                 raise ValueError("Column 'Mehltauanfälligkeit' not found in sortenanfaelligkeit_df for merge.")

            df_merged = pd.merge(
                df_melted,
                sortenanfaelligkeit_df[['Sorte', 'Mehltauanfälligkeit']], # Only need these columns
                on="Mehltauanfälligkeit",
                how="inner" # Use inner join to only keep valid combinations
            )

            if df_merged.empty:
                logger.warning("Behandlungsintervall dataframe is empty after merging with Sortenanfälligkeit.")
                return pd.DataFrame(columns=['Mittel', 'Sorte', 'Behandlungsintervall_min', 'Behandlungsintervall_max'])


            # Pivot to get min/max columns
            df_pivoted = df_merged.pivot_table(
                index=['Mittel', 'Sorte'],
                columns='Range',
                values='Behandlungsintervall',
                aggfunc='first' # Use 'first' assuming one value per Mittel/Sorte/Range
            ).reset_index()

            # Rename columns
            df_pivoted = df_pivoted.rename(columns={
                'min': 'Behandlungsintervall_min',
                'max': 'Behandlungsintervall_max'
            })

             # Ensure final columns exist, handle if pivot didn't create min/max
            final_cols = ['Mittel', 'Sorte', 'Behandlungsintervall_min', 'Behandlungsintervall_max']
            for col in final_cols:
                if col not in df_pivoted.columns:
                    df_pivoted[col] = pd.NA # Or appropriate default like 0 or np.nan

            logger.info(f"Processed Behandlungsintervall data ready. Shape: {df_pivoted.shape}")
            return df_pivoted[final_cols] # Return only necessary columns

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading or processing Behandlungsintervall data: {e}", exc_info=True)
            raise ProcessingError(f"Failed to process {file_path}: {e}") from e

    def load_all(self):
        """Loads all static data required."""
        logger.info("Loading all static data...")
        regen = self.load_regenbestaendigkeit()
        sorten = self.load_sortenanfaelligkeit()
        intervall = self.load_behandlungsintervall(sorten)
        logger.info("Static data loading complete.")
        return {
            "regen": regen,
            "sorten": sorten, # Keep if needed elsewhere, otherwise can be omitted
            "intervall": intervall
        }