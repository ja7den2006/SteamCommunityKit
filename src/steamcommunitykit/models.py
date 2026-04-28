from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import unquote
from typing import Any, Dict, List, Optional

from steamcommunitykit.exceptions import SteamValidationError


@dataclass
class QRAuthSession:
    client_id: int
    request_id: str
    interval: float
    challenge_url: str
    version: int = 1
    allowed_confirmations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CommunityCredentials:
    steam_id: str
    session_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    steam_login_secure: Optional[str] = None

    @classmethod
    def from_cookie_pair(
        cls,
        *,
        session_id: str,
        steam_login_secure: str,
    ) -> "CommunityCredentials":
        normalized_session_id = session_id.strip()
        normalized_cookie = steam_login_secure.strip()
        if not normalized_session_id:
            raise SteamValidationError("session_id must be a non-empty string.")
        if not normalized_cookie:
            raise SteamValidationError("steam_login_secure must be a non-empty string.")
        decoded_cookie = unquote(normalized_cookie)
        if "||" not in decoded_cookie:
            raise SteamValidationError(
                "steam_login_secure must contain an encoded SteamID and access token."
            )
        steam_id, access_token = decoded_cookie.split("||", 1)
        if not steam_id or not access_token:
            raise SteamValidationError(
                "steam_login_secure must contain both a SteamID and access token."
            )
        return cls(
            steam_id=steam_id,
            session_id=normalized_session_id,
            access_token=access_token,
            steam_login_secure=normalized_cookie,
        )

    @property
    def steam_login_secure_value(self) -> str:
        if self.steam_login_secure:
            return self.steam_login_secure
        if self.access_token:
            return f"{self.steam_id}%7C%7C{self.access_token}"
        raise SteamValidationError(
            "Community credentials require either steam_login_secure or access_token."
        )


@dataclass
class CredentialLoginResult:
    steam_id: str
    account_name: str
    client_id: int
    request_id: str
    access_token: str
    refresh_token: str
    had_remote_interaction: bool = False


@dataclass
class AvailabilityResult:
    field_id: Optional[str]
    available: bool
    message: str
    raw_text: str


@dataclass
class CreatedGroup:
    name: str
    abbreviation: str
    group_id: str
    group_id64: str
    group_url: str
    public: bool
