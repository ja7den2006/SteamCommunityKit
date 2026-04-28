from __future__ import annotations

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint64


class BroadcastService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IBroadcastService"

    def post_game_data_frame(self, app_id, steam_id, broadcast_id, frame_data: str) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/PostGameDataFrame/v1/",
            require_api_key=True,
            service_payload={
                "appid": validate_app_id(app_id),
                "steamid": validate_steam_id(steam_id),
                "broadcast_id": validate_uint64(broadcast_id, "broadcast_id"),
                "frame_data": ensure_not_blank(frame_data, "frame_data"),
            },
        )
