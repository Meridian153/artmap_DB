from __future__ import annotations

import time
from typing import Any

import requests

from src.reception.infra.external_apis.exceptions import ApiRateLimitException, ExternalApiException
from src.shared_kernel.infra.log.logger import setup_logger


class BaseApiClient:
    def __init__(self, base_url: str, api_name: str, rate_limit_delay: float = 0.1):
        self.base_url = base_url
        self.api_name = api_name
        self.rate_limit_delay = rate_limit_delay
        self.logger = setup_logger(f"{api_name}Client")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ArtMap/1.0 (Educational Project)"})

    def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None, method: str = "GET"
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"

        try:
            time.sleep(self.rate_limit_delay)

            if method == "GET":
                response = self.session.get(url, params=params, timeout=30)
            else:
                response = self.session.request(method, url, params=params, timeout=30)

            if response.status_code == 429:
                raise ApiRateLimitException(self.api_name)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {url}, Error: {str(e)}")
            raise ExternalApiException(self.api_name, str(e))

    def close(self):
        self.session.close()
