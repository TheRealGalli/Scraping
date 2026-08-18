import logging
from typing import Set, List, Dict, Any
import google.auth
import gspread

from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class SheetsService:
    def __init__(self, spreadsheet_id: str = None, sheet_name: str = None):
        self.spreadsheet_id = spreadsheet_id or settings.SPREADSHEET_ID
        self.sheet_name = sheet_name or settings.SHEET_NAME
        self.client = None
        self.sheet = None

    def _get_client(self):
        if not self.client:
            import os
            import json
            from google.oauth2 import service_account

            # 1. Check for JSON content in environment variable
            sa_json_env = os.environ.get("GCP_SA_KEY") or os.environ.get("SERVICE_ACCOUNT_JSON")
            if sa_json_env:
                try:
                    info = json.loads(sa_json_env)
                    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
                    self.client = gspread.authorize(credentials)
                    logger.info("Authorized SheetsService using service account JSON from environment variable.")
                    return self.client
                except Exception as e:
                    logger.warning(f"Could not load credentials from SA JSON environment variable: {e}")

            # 2. Check for file path in GOOGLE_APPLICATION_CREDENTIALS or local json files
            sa_file_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            possible_files = [sa_file_env] if sa_file_env else []
            possible_files.extend(["service_account.json", "credentials.json", "sa_key.json"])

            for file_path in possible_files:
                if file_path and os.path.exists(file_path):
                    try:
                        self.client = gspread.service_account(filename=file_path, scopes=SCOPES)
                        logger.info(f"Authorized SheetsService using service account file '{file_path}'.")
                        return self.client
                    except Exception as e:
                        logger.warning(f"Could not load credentials from file '{file_path}': {e}")

            # 3. Fallback to Google Application Default Credentials (ADC)
            credentials, _ = google.auth.default(scopes=SCOPES)
            if hasattr(credentials, "with_scopes"):
                credentials = credentials.with_scopes(SCOPES)
            self.client = gspread.authorize(credentials)
            logger.info("Authorized SheetsService using Google Default Credentials.")
        return self.client

    def _get_worksheet(self):
        if not self.sheet:
            client = self._get_client()
            spreadsheet = client.open_by_key(self.spreadsheet_id)
            try:
                self.sheet = spreadsheet.worksheet(self.sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                # If sheet doesn't exist, create it
                self.sheet = spreadsheet.add_worksheet(title=self.sheet_name, rows="1000", cols="9")
                self._ensure_headers()
        return self.sheet

    def _ensure_headers(self):
        """Ensures header row is present in the worksheet."""
        headers = ["Place ID", "Regione", "Provincia", "Città", "Settore", "Sito Web", "Email", "Stato Invio", "Data Invio", "Rating", "Recensioni"]
        existing = self.sheet.row_values(1)
        if not existing:
            self.sheet.append_row(headers)

    def get_existing_place_ids(self) -> Set[str]:
        """
        Reads Column A of the target sheet to retrieve all stored Place IDs.
        Returns a set of Place ID strings.
        """
        try:
            ws = self._get_worksheet()
            col_a_values = ws.col_values(1)
            # Exclude header if present ("Place ID")
            place_ids = set()
            for val in col_a_values:
                val_clean = val.strip()
                if val_clean and val_clean.lower() != "place id":
                    place_ids.add(val_clean)
            logger.info(f"Loaded {len(place_ids)} existing Place IDs from Google Sheet '{self.sheet_name}'.")
            return place_ids
        except Exception as e:
            logger.error(f"Error fetching existing Place IDs from Google Sheet: {type(e).__name__} - {e}")
            return set()

    def append_lead_records(self, records: List[Dict[str, Any]]) -> int:
        """
        Appends a list of lead records to the worksheet.
        Each record dictionary contains:
        place_id, region, province, city, sector, website, email, rating, user_rating_count
        
        Formats to 11 columns:
        1. Place ID
        2. Regione
        3. Provincia
        4. Città
        5. Settore
        6. Sito Web
        7. Email
        8. Stato Invio ("Da inviare" if email present else "Nessuna email")
        9. Data Invio (empty)
        10. Rating
        11. Recensioni
        """
        if not records:
            return 0

        rows_to_append = []
        for r in records:
            email = (r.get("email") or "").strip()
            stato_invio = "Da inviare" if email else "Nessuna email"
            rating_val = r.get("rating", "")
            rating_str = str(rating_val) if rating_val is not None else ""
            reviews_val = r.get("user_rating_count", "")
            reviews_str = str(reviews_val) if reviews_val is not None else ""
            
            row = [
                r.get("place_id", "").strip(),
                r.get("region", "").strip(),
                r.get("province", "").strip(),
                r.get("city", "").strip(),
                r.get("sector", "").strip(),
                r.get("website", "").strip(),
                email,
                stato_invio,
                "",  # Data Invio (empty)
                rating_str,
                reviews_str
            ]
            rows_to_append.append(row)

        try:
            ws = self._get_worksheet()
            ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            logger.info(f"Successfully appended {len(rows_to_append)} rows to Google Sheet '{self.sheet_name}'.")
            return len(rows_to_append)
        except Exception as e:
            logger.error(f"Error appending rows to Google Sheet: {type(e).__name__} - {e}")
            return 0

    def get_pending_leads(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Reads worksheet and returns rows where Col G (Email) is present
        and Col H (Stato Invio) is set to 'Da inviare'.
        Returns list of dicts with 1-based row_index and lead fields.
        """
        try:
            ws = self._get_worksheet()
            all_values = ws.get_all_values()
            if not all_values:
                return []

            pending_leads = []
            # Index 0 is header row (row 1 in Sheets)
            for idx, row in enumerate(all_values[1:], start=2):
                # Ensure row has at least 8 elements
                padded_row = row + [""] * max(0, 9 - len(row))
                email = padded_row[6].strip()
                status = padded_row[7].strip()

                if email and status == "Da inviare":
                    pending_leads.append({
                        "row_index": idx,
                        "place_id": padded_row[0].strip(),
                        "region": padded_row[1].strip(),
                        "province": padded_row[2].strip(),
                        "city": padded_row[3].strip(),
                        "sector": padded_row[4].strip(),
                        "website": padded_row[5].strip(),
                        "email": email,
                        "status": status
                    })
                    if len(pending_leads) >= limit:
                        break

            logger.info(f"Found {len(pending_leads)} pending leads to send emails.")
            return pending_leads
        except Exception as e:
            logger.error(f"Error fetching pending leads from Google Sheet: {type(e).__name__} - {e}")
            return []

    def update_lead_status(self, row_index: int, success: bool, timestamp_str: str = "") -> bool:
        """
        Updates Col H (Stato Invio) and Col I (Data Invio) for a given row_index.
        - success=True -> Col H = "Inviato", Col I = timestamp_str
        - success=False -> Col H = "Errore Invio"
        """
        try:
            ws = self._get_worksheet()
            if success:
                new_status = "Inviato"
                # Update range H{row}:I{row}
                ws.update(range_name=f"H{row_index}:I{row_index}", values=[[new_status, timestamp_str]])
            else:
                new_status = "Errore Invio"
                ws.update(range_name=f"H{row_index}", values=[[new_status]])

            logger.info(f"Row {row_index} status updated to '{new_status}'.")
            return True
        except Exception as e:
            logger.error(f"Error updating status for row {row_index}: {e}")
            return False

    def get_matrix_index(self) -> int:
        """
        Reads stored matrix index from 'ConfigState' worksheet in Google Sheets.
        Defaults to 0 if not present or unreadable.
        """
        try:
            client = self._get_client()
            spreadsheet = client.open_by_key(self.spreadsheet_id)
            try:
                state_ws = spreadsheet.worksheet("ConfigState")
            except gspread.exceptions.WorksheetNotFound:
                state_ws = spreadsheet.add_worksheet(title="ConfigState", rows="10", cols="3")
                state_ws.append_row(["Key", "Value", "Last Updated"])
                state_ws.append_row(["matrix_index", "0", ""])
                return 0

            val = state_ws.acell("B2").value
            if val and str(val).strip().isdigit():
                idx = int(str(val).strip())
                logger.info(f"Loaded matrix_index={idx} from Google Sheets ConfigState tab.")
                return idx
            return 0
        except Exception as e:
            logger.warning(f"Could not read matrix_index from ConfigState sheet: {e}")
            return 0

    def update_matrix_index(self, next_index: int) -> bool:
        """
        Updates stored matrix index in 'ConfigState' worksheet cell B2.
        """
        try:
            client = self._get_client()
            spreadsheet = client.open_by_key(self.spreadsheet_id)
            try:
                state_ws = spreadsheet.worksheet("ConfigState")
            except gspread.exceptions.WorksheetNotFound:
                state_ws = spreadsheet.add_worksheet(title="ConfigState", rows="10", cols="3")
                state_ws.append_row(["Key", "Value", "Last Updated"])

            from services.time_filter import get_rome_time
            now_str = get_rome_time().strftime("%Y-%m-%d %H:%M:%S")
            state_ws.update(range_name="B2:C2", values=[[str(next_index), now_str]])
            logger.info(f"Updated Google Sheets ConfigState matrix_index to {next_index}.")
            return True
        except Exception as e:
            logger.error(f"Error updating matrix_index in ConfigState sheet: {e}")
            return False
