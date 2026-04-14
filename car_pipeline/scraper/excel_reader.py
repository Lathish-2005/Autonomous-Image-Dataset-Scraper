"""
Excel Reader Module (Demo Version)
Reads all sheets from the Excel file. Each sheet represents one Car Make.
Extracts Manufacturer, Model Name, and URL to build the job queue.
"""

import os
import pandas as pd
import logging

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class ExcelReader:
    """Reads the multi-sheet Excel file and produces a clean list of scraping jobs."""

    def __init__(self, excel_path=None):
        self.excel_path = excel_path or config.EXCEL_PATH
        self.errors = []

    def read_jobs(self, filter_make=None, filter_model=None):
        """
        Read all sheets from the Excel file and return a list of job dictionaries.

        Args:
            filter_make: If set, only process this sheet (Make)
            filter_model: If set, only include this car model

        Returns:
            List of job dicts: [{ make, model, url, sheet_name, row_num }, ...]
        """
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(
                f"Excel file not found: {self.excel_path}\n"
                f"Place your Excel file at: {config.EXCEL_PATH}"
            )

        logger.info(f"Reading Excel file: {self.excel_path}")

        try:
            # Read all sheets into a dict of DataFrames: {sheet_name: df}
            all_sheets = pd.read_excel(self.excel_path, sheet_name=None, header=0)
        except Exception as e:
            raise RuntimeError(f"Failed to read Excel file: {e}")

        jobs = []
        skipped_empty = 0

        for sheet_name, df in all_sheets.items():
            make_clean = self._clean_name(sheet_name)

            def normalize(s):
                return str(s).lower().replace("_", " ").replace("-", " ").strip()

            if filter_make and normalize(make_clean) != normalize(filter_make):
                continue

            logger.info(f"Processing sheet [{sheet_name}] with {len(df)} rows")

            for row_idx, row in df.iterrows():
                row_num = row_idx + 2  # Excel row number (1-indexed + header)

                try:
                    # Look for the expected columns based on demo config
                    # If "Manufacturer" is missing, we fallback to the sheet name
                    make_raw = str(row.get(config.COL_MANUFACTURER, sheet_name)).strip()
                    model_raw = str(row[config.COL_MODEL_NAME]).strip()
                    url_raw = str(row[config.COL_URL]).strip()

                except KeyError as e:
                    self._log_error(sheet_name, row_num, f"Missing expected column: {e}")
                    continue

                if not url_raw or url_raw.lower() in ("nan", "none", ""):
                    skipped_empty += 1
                    continue

                # Fallback to sheet name if manufacturer column was empty/nan
                if not make_raw or make_raw.lower() in ("nan", "none"):
                    make_raw = sheet_name

                # Clean strings
                row_make_clean = self._clean_name(make_raw)
                model_clean = self._clean_name(model_raw)

                if filter_model and normalize(model_clean) != normalize(filter_model):
                    continue

                # Handle multiple URLs separated by commas but PRESERVE commas inside the URL (e.g., BMW configurator options)
                import re
                urls = [u.strip() for u in re.split(r'[,\s\n]+(?=https?://)', url_raw) if u.strip()]

                for url in urls:
                    job = {
                        "sheet": sheet_name,
                        "row_num": row_num,
                        "make": row_make_clean,
                        "model": model_clean,
                        "make_folder": self._to_folder_name(row_make_clean),
                        "model_folder": self._to_folder_name(model_clean),
                        "url": url,
                        # Demo defaults for compatibility with rest of pipeline
                        "tier": 1,
                        "source_type": "Official Website",
                    }
                    jobs.append(job)

        logger.info(
            f"Job queue built: {len(jobs)} total active jobs | "
            f"Skipped {skipped_empty} empty URLs"
        )
        return jobs

    def _clean_name(self, name):
        """Apply title case to make/model names."""
        if not name or str(name).lower() in ("nan", "none"):
            return "Unknown"
        return str(name).strip().title()

    def _to_folder_name(self, name):
        """Convert name to folder-safe format: title case, spaces to underscores."""
        name = str(name).strip().title()
        name = name.replace(" ", "_")
        safe = ""
        for ch in name:
            if ch.isalnum() or ch in ("_", "-"):
                safe += ch
            elif ch == " ":
                safe += "_"
        return safe if safe else "Unknown"

    def _log_error(self, sheet, row_num, message):
        """Store an error for later writing to errors.txt."""
        entry = f"[{sheet}] ROW {row_num:<5} — {message}"
        self.errors.append(entry)
        logger.warning(entry)

    def write_errors(self, path=None):
        """Write all collected errors to the errors log file."""
        path = path or config.ERRORS_LOG_PATH
        if not self.errors:
            return
            
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for err in self.errors:
                f.write(err + "\n")
        logger.info(f"Wrote {len(self.errors)} error entries to {path}")

    def get_job_summary(self, jobs):
        """Return a summary dict of the job queue."""
        makes = set(j["make"] for j in jobs)
        models = set(f"{j['make']}_{j['model']}" for j in jobs)
        sheets = set(j["sheet"] for j in jobs)

        return {
            "total_jobs": len(jobs),
            "unique_makes": len(makes),
            "unique_models": len(models),
            "sheets_processed": len(sheets),
        }
