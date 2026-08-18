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
            credentials, _ = google.auth.default(scopes=SCOPES)
            self.client = gspread.authorize(credentials)
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
        headers = ["Place ID", "Regione", "Provincia", "Città", "Settore", "Sito Web", "Email", "Stato Invio", "Data Invio"]
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
        place_id, region, province, city, sector, website, email
        
        Formats to 9 columns:
        1. Place ID
        2. Regione
        3. Provincia
        4. Città
        5. Settore
        6. Sito Web
        7. Email
        8. Stato Invio ("Da inviare" if email present else "Nessuna email")
        9. Data Invio (empty)
        """
        if not records:
            return 0

        rows_to_append = []
        for r in records:
            email = (r.get("email") or "").strip()
            stato_invio = "Da inviare" if email else "Nessuna email"
            
            row = [
                r.get("place_id", "").strip(),
                r.get("region", "").strip(),
                r.get("province", "").strip(),
                r.get("city", "").strip(),
                r.get("sector", "").strip(),
                r.get("website", "").strip(),
                email,
                stato_invio,
                ""  # Data Invio (empty)
            ]
            rows_to_append.append(row)

        try:
            ws = self._get_worksheet()
            ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            logger.info(f"Successfully appended {len(rows_to_append)} rows to Google Sheet '{self.sheet_name}'.")
            return len(rows_to_append)
        except Exception as e:
            logger.error(f"Error appending rows to Google Sheet: {e}")
            raise e

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
