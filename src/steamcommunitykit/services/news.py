from __future__ import annotations

import re
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

    @staticmethod
    def _strip_html(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", value or "")).strip()

    def get_news_summary(
        self,
        app_id,
        *,
        count: Optional[int] = None,
        max_length: Optional[int] = None,
        end_date: Optional[int] = None,
        feeds: Optional[str] = None,
        include_raw_contents: bool = False,
    ) -> dict:
        payload = self.get_news_for_app(
            app_id,
            count=count,
            max_length=max_length,
            end_date=end_date,
            feeds=feeds,
        )
        appnews = payload.get("appnews", {})
        items = []
        for item in appnews.get("newsitems", []):
            normalized = {
                "gid": item.get("gid"),
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "author": item.get("author") or "",
                "feed": item.get("feedlabel") or item.get("feedname") or "",
                "is_external_url": item.get("is_external_url"),
                "date": item.get("date"),
                "contents": self._strip_html(item.get("contents", "")),
                "raw": item,
            }
            if include_raw_contents:
                normalized["raw_contents"] = item.get("contents", "")
            items.append(normalized)
        return {
            "app_id": appnews.get("appid"),
            "items": items,
            "count": len(items),
            "raw": payload,
        }
