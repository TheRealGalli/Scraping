"""Bounded retries for explicit Sheets quota rejections, without replaying timeouts."""
import logging
import time

from gspread.exceptions import APIError
from gspread.http_client import HTTPClient

logger = logging.getLogger(__name__)


class QuotaRetryHTTPClient(HTTPClient):
    # Cross a full quota minute before giving up; no request values in logs.
    RETRY_DELAYS = (5, 10, 20, 40)

    def request(self, *args, **kwargs):
        for attempt in range(len(self.RETRY_DELAYS) + 1):
            try:
                return super().request(*args, **kwargs)
            except APIError as exc:
                if exc.response.status_code != 429 or attempt == len(self.RETRY_DELAYS):
                    raise
                delay = self.RETRY_DELAYS[attempt]
                logger.warning("Sheets quota exceeded; retry %s in %ss", attempt + 1, delay)
                time.sleep(delay)
