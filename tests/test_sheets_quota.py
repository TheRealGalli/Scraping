from unittest.mock import Mock

import pytest
from gspread.exceptions import APIError
from gspread.http_client import HTTPClient

from services.campaign_sheets import CampaignSheets
from services.sheets_http import QuotaRetryHTTPClient


def api_error(status):
    response = Mock(status_code=status)
    response.json.return_value = {"error": {"code": status, "message": "test", "status": "RESOURCE_EXHAUSTED"}}
    return APIError(response)


def test_quota_retry_crosses_minute_and_succeeds_without_changing_request(monkeypatch):
    expected = object()
    request = Mock(side_effect=[api_error(429)]*4 + [expected])
    monkeypatch.setattr(HTTPClient, "request", request)
    sleep = Mock()
    monkeypatch.setattr("services.sheets_http.time.sleep", sleep)
    client = object.__new__(QuotaRetryHTTPClient)
    assert client.request("get", "test", params={"fields": "sheets"}) is expected
    assert [c.args[0] for c in sleep.call_args_list] == [5, 10, 20, 40]
    assert request.call_count == 5
    assert all(c.args == ("get", "test") and c.kwargs == {"params": {"fields": "sheets"}} for c in request.call_args_list)


def test_quota_retry_is_bounded(monkeypatch):
    request = Mock(side_effect=api_error(429))
    monkeypatch.setattr(HTTPClient, "request", request)
    monkeypatch.setattr("services.sheets_http.time.sleep", Mock())
    with pytest.raises(APIError):
        object.__new__(QuotaRetryHTTPClient).request("get", "test")
    assert request.call_count == 5


@pytest.mark.parametrize("error", [api_error(403), api_error(500), TimeoutError("ambiguous write")])
def test_other_failures_are_not_replayed(monkeypatch, error):
    request, sleep = Mock(side_effect=error), Mock()
    monkeypatch.setattr(HTTPClient, "request", request)
    monkeypatch.setattr("services.sheets_http.time.sleep", sleep)
    with pytest.raises(type(error)):
        object.__new__(QuotaRetryHTTPClient).request("post", "test")
    assert request.call_count == 1
    sleep.assert_not_called()


def test_sheet_handles_cached_but_manual_values_always_fresh():
    book = Mock()
    book.worksheet.return_value.get_all_values.side_effect = [[["FALSE"]], [["TRUE"]]]
    sheets = CampaignSheets(book)
    assert sheets.rows("ControlloInvii") == [["FALSE"]]
    assert sheets.rows("ControlloInvii") == [["TRUE"]]
    book.worksheet.assert_called_once_with("ControlloInvii")
    assert book.worksheet.return_value.get_all_values.call_count == 2


def test_ensure_reuses_listed_handles_without_metadata_lookups():
    from services.campaign_sheets import HEADERS
    from services.campaign_catalog import RULE_VERSION
    book = Mock()
    tabs = {}
    for name, headers in HEADERS.items():
        tab = Mock(title=name)
        tab.row_values.return_value = headers
        tabs[name] = tab
    tabs["RegoleSettori"].get_all_values.return_value = [HEADERS["RegoleSettori"], ["consulenza", "Studi Professionali", RULE_VERSION]]
    book.worksheets.return_value = list(tabs.values())
    sheets = CampaignSheets(book)
    sheets.ensure()
    sheets.rows("ControlloInvii")
    book.worksheet.assert_not_called()
