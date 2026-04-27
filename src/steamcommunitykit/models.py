from __future__ import annotations

from dataclasses import dataclass, field
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
    steam_login_secure: Optional[str] = None

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
