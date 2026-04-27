from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import validate_app_id


class NewsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamNews"

    def get_news_for_app(
        self,
        app_id,
        *,
        count: Optional[int] = None,
        max_length: Optional[int] = None,
        end_date: Optional[int] = None,
        feeds: Optional[str] = None,
    ) -> dict:
        params = {"appid": validate_app_id(app_id)}
        if count is not None:
            params["count"] = int(count)
        if max_length is not None:
            params["maxlength"] = int(max_length)
        if end_date is not None:
            params["enddate"] = int(end_date)
        if feeds:
            params["feeds"] = feeds
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetNewsForApp/v2/",
            params=params,
        )

    def get_news_for_app_authed(
        self,
        app_id,
        *,
        count: Optional[int] = None,
        max_length: Optional[int] = None,
        end_date: Optional[int] = None,
        feeds: Optional[str] = None,
    ) -> dict:
        params = {"appid": validate_app_id(app_id)}
        if count is not None:
            params["count"] = int(count)
        if max_length is not None:
            params["maxlength"] = int(max_length)
        if end_date is not None:
            params["enddate"] = int(end_date)
        if feeds:
            params["feeds"] = feeds
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetNewsForAppAuthed/v2/",
            params=params,
            require_api_key=True,
        )
