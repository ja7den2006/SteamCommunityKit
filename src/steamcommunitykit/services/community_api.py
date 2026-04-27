from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint32, validate_uint64


class CommunityAPIService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamCommunity"

    def report_abuse(
        self,
        actor_steam_id,
        target_steam_id,
        app_id,
        abuse_type: int,
        content_type: int,
        description: str,
        *,
        gid: Optional[str] = None,
    ) -> dict:
        data = {
            "steamidActor": validate_steam_id(actor_steam_id, "actor_steam_id"),
            "steamidTarget": validate_steam_id(target_steam_id, "target_steam_id"),
            "appid": validate_app_id(app_id),
            "abuseType": validate_uint32(abuse_type, "abuse_type"),
            "contentType": validate_uint32(content_type, "content_type"),
            "description": ensure_not_blank(description, "description"),
        }
        if gid is not None:
            data["gid"] = validate_uint64(gid, "gid")
        return self.transport.request(
            "POST",
            f"{self.base_url}/ReportAbuse/v1/",
            data=data,
            require_api_key=True,
        )
