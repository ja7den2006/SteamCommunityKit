class SteamError(Exception):
    """Base exception for the package."""


class SteamValidationError(SteamError):
    """Raised when user-provided input is invalid before a request is sent."""


class SteamNetworkError(SteamError):
    """Raised for transport-level failures."""


class SteamResponseError(SteamError):
    """Raised when Steam returns a malformed or unexpected response."""


class SteamHTTPError(SteamError):
    """Raised for HTTP responses with an error status."""

    def __init__(self, message: str, *, status_code: int, payload=None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class SteamAuthenticationError(SteamHTTPError):
    """Raised when authentication or authorization fails."""


class SteamNotFoundError(SteamHTTPError):
    """Raised when a resource cannot be found."""


class SteamRateLimitError(SteamHTTPError):
    """Raised when Steam rate-limits the request."""


class SteamAPIError(SteamHTTPError):
    """Raised for non-auth API failures."""

