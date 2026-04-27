from __future__ import annotations

from typing import Iterable, Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint32


class PublishedItemSearchService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamPublishedItemSearch"

    def ranked_by_publication_order(
        self,
        steam_id,
        app_id,
        *,
        start_index: int = 0,
        count: int = 10,
        tags: Optional[Iterable[str]] = None,
        user_tags: Optional[Iterable[str]] = None,
        has_app_admin_access: Optional[bool] = None,
        file_type: Optional[int] = None,
    ) -> dict:
        return self._search(
            "RankedByPublicationOrder",
            steam_id,
            app_id,
            start_index=start_index,
            count=count,
            tags=tags,
            user_tags=user_tags,
            has_app_admin_access=has_app_admin_access,
            file_type=file_type,
        )

    def ranked_by_trend(
        self,
        steam_id,
        app_id,
        *,
        start_index: int = 0,
        count: int = 10,
        days: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
        user_tags: Optional[Iterable[str]] = None,
        has_app_admin_access: Optional[bool] = None,
        file_type: Optional[int] = None,
    ) -> dict:
        return self._search(
            "RankedByTrend",
            steam_id,
            app_id,
            start_index=start_index,
            count=count,
            days=days,
            tags=tags,
            user_tags=user_tags,
            has_app_admin_access=has_app_admin_access,
            file_type=file_type,
        )

    def ranked_by_vote(
        self,
        steam_id,
        app_id,
        *,
        start_index: int = 0,
        count: int = 10,
        tags: Optional[Iterable[str]] = None,
        user_tags: Optional[Iterable[str]] = None,
        has_app_admin_access: Optional[bool] = None,
        file_type: Optional[int] = None,
    ) -> dict:
        return self._search(
            "RankedByVote",
            steam_id,
            app_id,
            start_index=start_index,
            count=count,
            tags=tags,
            user_tags=user_tags,
            has_app_admin_access=has_app_admin_access,
            file_type=file_type,
        )

    def result_set_summary(
        self,
        steam_id,
        app_id,
        *,
        tags: Optional[Iterable[str]] = None,
        user_tags: Optional[Iterable[str]] = None,
        has_app_admin_access: Optional[bool] = None,
        file_type: Optional[int] = None,
    ) -> dict:
        return self._search(
            "ResultSetSummary",
            steam_id,
            app_id,
            start_index=None,
            count=None,
            tags=tags,
            user_tags=user_tags,
            has_app_admin_access=has_app_admin_access,
            file_type=file_type,
        )

    def _search(
        self,
        method_name: str,
        steam_id,
        app_id,
        *,
        start_index: Optional[int],
        count: Optional[int],
        tags: Optional[Iterable[str]],
        user_tags: Optional[Iterable[str]],
        has_app_admin_access: Optional[bool],
        file_type: Optional[int],
        days: Optional[int] = None,
    ) -> dict:
        normalized_tags = [ensure_not_blank(tag, "tag") for tag in (tags or [])]
        normalized_user_tags = [ensure_not_blank(tag, "user_tag") for tag in (user_tags or [])]
        data = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
            "tagcount": len(normalized_tags),
            "usertagcount": len(normalized_user_tags),
        }
        if start_index is not None:
            data["startidx"] = validate_uint32(start_index, "start_index", allow_zero=True)
        if count is not None:
            data["count"] = validate_uint32(count, "count")
        if has_app_admin_access is not None:
            data["hasappadminaccess"] = int(has_app_admin_access)
        if file_type is not None:
            data["fileType"] = validate_uint32(file_type, "file_type", allow_zero=True)
        if days is not None:
            data["days"] = validate_uint32(days, "days")
        for index, tag in enumerate(normalized_tags):
            data["tag[{0}]".format(index)] = tag
        for index, tag in enumerate(normalized_user_tags):
            data["usertag[{0}]".format(index)] = tag
        return self.transport.request(
            "POST",
            f"{self.base_url}/{method_name}/v1/",
            data=data,
            require_api_key=True,
        )
