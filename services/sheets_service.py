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

LEAD_HEADERS = ["Place ID", "Regione", "Provincia", "Città", "Settore", "Sito Web", "Email", "Stato Invio", "Data Invio", "Rating", "Recensioni"]
# Optional enrichment in L:P; A:K keep their historical meaning.
SIGNAL_HEADERS = ["Categoria Google", "Foto Google", "Segnali sito", "Aggancio", "Google Maps"]

class SheetsService:
    def __init__(self, spreadsheet_id: str = None, sheet_name: str = None):
        self.spreadsheet_id = spreadsheet_id or settings.SPREADSHEET_ID
        self.sheet_name = sheet_name or settings.SHEET_NAME
        self.client = None
        self.sheet = None
        self._state_sheet = None

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
                self.sheet = spreadsheet.add_worksheet(title=self.sheet_name, rows="1000", cols=str(len(LEAD_HEADERS + SIGNAL_HEADERS)))
                self._ensure_headers()
        return self.sheet

    def _ensure_headers(self):
        """Ensures header row is present in the worksheet."""
        headers = LEAD_HEADERS + SIGNAL_HEADERS
        existing = self.sheet.row_values(1)
        if not existing:
            self.sheet.append_row(headers)

    def get_existing_place_ids(self, strict=False) -> Set[str]:
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
            if strict:
                raise
            return set()

    def append_lead_records(self, records: List[Dict[str, Any]], strict=False, signals=False) -> int:
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
        12-16. SIGNAL_HEADERS, only when signals=True (L:P headers verified)
        """
        if not records:
            return 0

        rows_to_append = []
        for r in records:
            email = (r.get("email") or "").strip()
            stato_invio = "Da inviare" if email else "Nessuna email"
            rating_val = r.get("rating", "")
            rating_value = rating_val if rating_val is not None else ""
            reviews_val = r.get("user_rating_count", "")
            reviews_value = reviews_val if reviews_val is not None else ""
            
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
                rating_value,
                reviews_value
            ]
            if signals:
                photos = r.get("google_photos")
                row += [
                    (r.get("google_category") or "").strip(),
                    photos if photos is not None else "",
                    (r.get("site_signals") or "").strip(),
                    (r.get("hook") or "").strip(),
                    (r.get("maps_url") or "").strip(),
                ]
            rows_to_append.append(row)

        try:
            ws = self._get_worksheet()
            ws.append_rows(rows_to_append, value_input_option="RAW")
            logger.info(f"Successfully appended {len(rows_to_append)} rows to Google Sheet '{self.sheet_name}'.")
            return len(rows_to_append)
        except Exception as e:
            logger.error(f"Error appending rows to Google Sheet: {type(e).__name__} - {e}")
            if strict:
                raise
            return 0

    def get_existing_sent_emails(self) -> Set[str]:
        """
        Reads the worksheet and returns a set of email addresses that have
        already been sent (Col H / Stato Invio == 'Inviato').

        Used by the email sender to avoid sending duplicate emails to the same
        address found in different store locations (place IDs).
        """
        try:
            ws = self._get_worksheet()
            all_values = ws.get_all_values()
            if not all_values:
                return set()

            sent_emails: Set[str] = set()
            # Row 0 is the header; data starts at row index 1
            for row in all_values[1:]:
                padded_row = row + [""] * max(0, 9 - len(row))
                email = padded_row[6].strip().lower()
                status = padded_row[7].strip()
                if email and status == "Inviato":
                    sent_emails.add(email)

            logger.info(f"Loaded {len(sent_emails)} already-sent email addresses from Google Sheet '{self.sheet_name}'.")
            return sent_emails
        except Exception as e:
            logger.error(f"Error fetching sent emails from Google Sheet: {type(e).__name__} - {e}")
            return set()

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

    def update_lead_status(self, row_index: int, success: bool, timestamp_str: str = "", mark_as: str = "") -> bool:
        """
        Updates Col H (Stato Invio) and Col I (Data Invio) for a given row_index.
        - mark_as (non-empty) -> Col H = mark_as value (e.g. 'Duplicato Email'), Col I unchanged
        - success=True        -> Col H = "Inviato", Col I = timestamp_str
        - success=False       -> Col H = "Errore Invio"
        """
        try:
            ws = self._get_worksheet()
            if mark_as:
                # Custom status (e.g. 'Duplicato Email') — leave Col I untouched
                ws.update(range_name=f"H{row_index}", values=[[mark_as]])
                new_status = mark_as
            elif success:
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

    def update_matrix_index(self, next_index: int, strict=False) -> bool:
        """
        Updates stored matrix index in 'ConfigState' worksheet cell B2.
        """
        try:
            state_ws = self._state_sheet
            if state_ws is None:
                client = self._get_client()
                spreadsheet = client.open_by_key(self.spreadsheet_id)
                try:
                    state_ws = spreadsheet.worksheet("ConfigState")
                except gspread.exceptions.WorksheetNotFound:
                    if strict:
                        raise
                    state_ws = spreadsheet.add_worksheet(title="ConfigState", rows="10", cols="3")
                    state_ws.append_row(["Key", "Value", "Last Updated"])

            from services.time_filter import get_rome_time
            now_str = get_rome_time().strftime("%Y-%m-%d %H:%M:%S")
            state_ws.update(range_name="B2:C2", values=[[str(next_index), now_str]])
            logger.info(f"Updated Google Sheets ConfigState matrix_index to {next_index}.")
            return True
        except Exception as e:
            logger.error(f"Error updating matrix_index in ConfigState sheet: {e}")
            if strict:
                raise
            return False

    def scraper_state(self, expand=False):
        """Validate the named source and cursor before any paid Places request."""
        from services.geo_matrix import CURRENT_SECTOR_PROFILE, convert_matrix_offset, sector_names_for_profile
        from services.time_filter import get_rome_time

        if self.sheet_name != "Italy":
            raise ValueError("This scraper must write to the Italy source sheet")
        book = self._get_client().open_by_key(self.spreadsheet_id)
        source_ws = book.worksheet(self.sheet_name)
        header = source_ws.row_values(1)
        if header[:9] != LEAD_HEADERS[:9]:
            raise ValueError("Unexpected source headers: " + self.sheet_name)
        signals = header[11:16] == SIGNAL_HEADERS
        # Claim only empty header cells; manual columns in L:P disable enrichment.
        claim_signals = expand and not signals and not any(str(cell).strip() for cell in header[11:16])
        state_ws = book.worksheet("ConfigState")
        rows = state_ws.get_all_values()
        if len(rows) < 2 or len(rows[1]) < 2 or rows[1][0] != "matrix_index" or not str(rows[1][1]).strip().isdigit():
            raise ValueError("Missing or invalid saved scraper cursor; refusing to restart at zero")
        index = int(str(rows[1][1]).strip())
        profile = "legacy_v1"
        if len(rows) > 2 and any(rows[2]):
            if rows[2][0] != "sector_profile" or len(rows[2]) < 2:
                raise ValueError("Unexpected ConfigState row 3")
            profile = rows[2][1]
        sector_names_for_profile(profile)
        if expand and profile != CURRENT_SECTOR_PROFILE:
            index = convert_matrix_offset(index, settings.CYCLES_PER_CITY, profile, CURRENT_SECTOR_PROFILE)
            stamp = get_rome_time().strftime("%Y-%m-%d %H:%M:%S")
            state_ws.update(range_name="A2:C3", values=[
                ["matrix_index", str(index), stamp], ["sector_profile", CURRENT_SECTOR_PROFILE, stamp],
            ], value_input_option="RAW")
            profile = CURRENT_SECTOR_PROFILE
        if claim_signals:
            source_ws.update(range_name="L1:P1", values=[SIGNAL_HEADERS], value_input_option="RAW")
            signals = True
        self.sheet, self._state_sheet = source_ws, state_ws
        return {"sheet": self.sheet_name, "profile": profile, "index": index,
                "sectors": sector_names_for_profile(profile), "signals": signals}


    def get_matrix_profile(self) -> str:
        # Fail closed on access errors: do not reinterpret an expanded cursor.
        book = self._get_client().open_by_key(self.spreadsheet_id)
        state = book.worksheet("ConfigState").get_all_values()
        if len(state) < 3 or not any(state[2]):
            return "legacy_v1"
        if state[2][0] != "sector_profile":
            raise ValueError("ConfigState row 3 already in use; inspect before migration")
        profile = state[2][1] if len(state[2]) > 1 else ""
        from services.geo_matrix import sector_names_for_profile
        sector_names_for_profile(profile)
        return profile
