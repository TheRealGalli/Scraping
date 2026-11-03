from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from config import settings
from services.geo_matrix import generate_search_targets
from services.sheets_service import LEAD_HEADERS, SheetsService
from services import worker


class Worksheet:
    def __init__(self, title, rows, writes):
        self.title, self.rows, self.writes = title, deepcopy(rows), writes
        self.fail_read = self.fail_append = self.fail_update = False

    def row_values(self, row):
        return list(self.rows[row - 1])

    def col_values(self, col):
        if self.fail_read:
            raise RuntimeError("temporary read failure")
        return [row[col - 1] for row in self.rows if len(row) >= col]

    def get_all_values(self):
        return deepcopy(self.rows)

    def append_rows(self, rows, value_input_option):
        assert value_input_option == "RAW"
        if self.fail_append:
            raise RuntimeError("temporary append failure")
        self.rows.extend(deepcopy(rows))
        self.writes.append((self.title, "append"))

    def update(self, range_name, values, value_input_option=None):
        if self.fail_update:
            raise RuntimeError("temporary cursor failure")
        if range_name == "A2:C3":
            while len(self.rows) < 3:
                self.rows.append([])
            self.rows[1:3] = deepcopy(values)
        elif range_name == "B2:C2":
            self.rows[1][1:3] = deepcopy(values[0])
        else:
            raise AssertionError(range_name)
        self.writes.append((self.title, range_name))


@pytest.fixture
def sheets(monkeypatch):
    monkeypatch.setattr(settings, "SHEET_NAME", "Italy")
    writes = []
    # Italy is intentionally the last tab: selection must use its name.
    tabs = {name: Worksheet(name, [[name, "preserve"]], writes)
            for name in ("Contatti", "Invii", "Campagne", "Panoramica", "Esclusioni")}
    tabs["ConfigState"] = Worksheet("ConfigState", [
        ["Key", "Value", "Last Updated"], ["matrix_index", "11", "old"],
        ["sector_profile", "expanded_v3", "old"], ["manual-note", "keep", ""],
    ], writes)
    tabs["Italy"] = Worksheet("Italy", [LEAD_HEADERS, [
        "old-place", "Lombardia", "Milano", "Milano", "Hospitality", "https://old.it",
        "info@old.it", "Inviato", "2026-10-23 10:00", 4.8, 90,
    ]], writes)
    book = MagicMock()
    book.worksheet.side_effect = tabs.__getitem__
    client = MagicMock()
    client.open_by_key.return_value = book
    service = SheetsService()
    monkeypatch.setattr(service, "_get_client", lambda: client)
    return service, tabs, writes


def mock_worker(monkeypatch, service, responses):
    monkeypatch.setattr(worker, "is_night_time", lambda: False)
    monkeypatch.setattr(worker, "SheetsService", lambda: service)
    places = MagicMock()
    places.search_places.side_effect = responses
    monkeypatch.setattr(worker, "PlacesService", lambda: places)
    web = MagicMock()
    web.scrape_website_content.return_value = "info@business.it"
    monkeypatch.setattr(worker, "WebScraper", lambda: web)
    extractor = MagicMock()
    extractor.extract_email_with_regex.return_value = "info@business.it"
    monkeypatch.setattr(worker, "EmailExtractor", lambda: extractor)
    monkeypatch.setattr(settings, "ENABLE_GEMINI_GROUNDING", False)
    monkeypatch.setattr(settings, "MAX_SEARCH_QUERIES_PER_RUN", 1)
    monkeypatch.setattr(settings, "SLEEP_BETWEEN_CALLS", 0)
    return places


def place(pid):
    return {"place_id": pid, "name": "Example", "website": "https://example.it",
            "rating": 4.3, "user_rating_count": 14}


def test_worker_appends_new_sectors_only_to_italy_and_preserves_other_tabs(sheets, monkeypatch):
    service, tabs, writes = sheets
    before = deepcopy({name: tab.rows for name, tab in tabs.items()})
    places = mock_worker(monkeypatch, service, [[place("old-place"), place("jeweller")], [place("dentist")]])
    worker.run_lead_generation_task()
    worker.run_lead_generation_task()
    rows = tabs["Italy"].rows
    assert rows[:2] == before["Italy"]
    assert [row[4] for row in rows[2:]] == ["Gioiellerie", "Studi Dentistici"]
    assert [row[0] for row in rows[2:]] == ["jeweller", "dentist"]
    assert all(len(row) == 11 for row in rows)
    assert rows[2][7:11] == ["Da inviare", "", 4.3, 14]
    assert tabs["ConfigState"].rows[1][1] == "13"
    assert tabs["ConfigState"].rows[3] == before["ConfigState"][3]
    assert writes == [("Italy", "append"), ("ConfigState", "B2:C2")] * 2
    for name in ("Contatti", "Invii", "Campagne", "Panoramica", "Esclusioni"):
        assert tabs[name].rows == before[name]
    assert places.search_places.call_count == 2


@pytest.mark.parametrize("profile,index", [("legacy_v1", 17), ("expanded_v2", 25)])
def test_profile_upgrade_preserves_next_city_and_sector_and_is_idempotent(sheets, profile, index):
    service, tabs, writes = sheets
    tabs["ConfigState"].rows[1][1] = str(index)
    tabs["ConfigState"].rows[2][1] = profile
    before = next(generate_search_targets(index, profile))
    upgraded = service.scraper_state(expand=True)
    assert upgraded["profile"] == "expanded_v3" and len(upgraded["sectors"]) == 13
    assert next(generate_search_targets(upgraded["index"], "expanded_v3"))[:4] == before[:4]
    assert service.scraper_state(expand=True) == upgraded
    assert writes == [("ConfigState", "A2:C3")]
    assert tabs["ConfigState"].rows[3] == ["manual-note", "keep", ""]


def test_failed_append_keeps_saved_target_for_retry(sheets, monkeypatch):
    service, tabs, writes = sheets
    tabs["Italy"].fail_append = True
    mock_worker(monkeypatch, service, [[place("new")]])
    with pytest.raises(RuntimeError, match="append failure"):
        worker.run_lead_generation_task()
    assert tabs["ConfigState"].rows[1][1] == "11"
    assert len(tabs["Italy"].rows) == 2 and not writes


def test_failed_cursor_update_does_not_duplicate_the_saved_italy_row_on_retry(sheets, monkeypatch):
    service, tabs, writes = sheets
    places = mock_worker(monkeypatch, service, [[place("new")], [place("new")]])
    tabs["ConfigState"].fail_update = True
    with pytest.raises(RuntimeError, match="cursor failure"):
        worker.run_lead_generation_task()
    assert len(tabs["Italy"].rows) == 3 and tabs["ConfigState"].rows[1][1] == "11"
    tabs["ConfigState"].fail_update = False
    worker.run_lead_generation_task()
    assert len(tabs["Italy"].rows) == 3 and tabs["ConfigState"].rows[1][1] == "12"
    assert writes.count(("Italy", "append")) == 1 and places.search_places.call_count == 2


def test_unreadable_place_ids_stop_before_any_maps_request(sheets, monkeypatch):
    service, tabs, writes = sheets
    places = mock_worker(monkeypatch, service, [])
    tabs["Italy"].fail_read = True
    with pytest.raises(RuntimeError, match="read failure"):
        worker.run_lead_generation_task()
    places.search_places.assert_not_called()
    assert not writes


@pytest.mark.parametrize("invalid", ["", "not-an-index", "-1"])
def test_invalid_cursor_never_restarts_the_search_from_zero(sheets, monkeypatch, invalid):
    service, tabs, writes = sheets
    places = mock_worker(monkeypatch, service, [])
    tabs["ConfigState"].rows[1][1] = invalid
    with pytest.raises(ValueError, match="saved scraper cursor"):
        worker.run_lead_generation_task()
    places.search_places.assert_not_called()
    assert not writes


def test_unexpected_source_headers_prevent_writing_to_another_kind_of_tab(sheets):
    service, tabs, writes = sheets
    tabs["Italy"].rows[0] = ["ID", "Email", "Campagne inviate"]
    with pytest.raises(ValueError, match="source headers"):
        service.scraper_state(expand=True)
    assert not writes


def test_scraper_rejects_an_environment_pointing_at_a_different_tab(sheets):
    service, _, writes = sheets
    service.sheet_name = "Contatti"
    with pytest.raises(ValueError, match="must write to the Italy"):
        service.scraper_state(expand=True)
    assert not writes


def test_scraper_check_prepares_profile_without_querying_places_or_changing_campaigns(sheets, monkeypatch, capsys):
    from scripts import campaign_admin
    service, tabs, writes = sheets
    monkeypatch.setattr("services.sheets_service.SheetsService", lambda: service)
    store = MagicMock()
    monkeypatch.setattr(campaign_admin, "FirestoreStore", store)
    campaign_admin.main(["scraper-check"])
    store.assert_not_called()
    output = capsys.readouterr().out
    assert '"status": "ready"' in output and '"sheet": "Italy"' in output
    assert "Gioiellerie" in output and "Studi Dentistici" in output
    assert not writes
