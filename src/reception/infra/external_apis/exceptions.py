class ExternalApiException(Exception):
    def __init__(self, api_name: str, message: str):
        self.api_name = api_name
        super().__init__(f"[{api_name}] External API error: {message}")


class ApiRateLimitException(ExternalApiException):
    def __init__(self, api_name: str):
        super().__init__(api_name, "Rate limit exceeded (HTTP 429)")
