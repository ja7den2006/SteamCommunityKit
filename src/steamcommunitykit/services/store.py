from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank


class StoreService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IStoreService"

    def get_app_list(
        self,
        *,
        if_modified_since: Optional[int] = None,
        have_description_language: Optional[str] = None,
        include_games: Optional[bool] = None,
        include_dlc: Optional[bool] = None,
        include_software: Optional[bool] = None,
        include_videos: Optional[bool] = None,
        include_hardware: Optional[bool] = None,
    ) -> dict:
        params = {}
        if if_modified_since is not None:
            params["if_modified_since"] = int(if_modified_since)
        if have_description_language:
            params["have_description_language"] = have_description_language
        if include_games is not None:
            params["include_games"] = int(include_games)
        if include_dlc is not None:
            params["include_dlc"] = int(include_dlc)
        if include_software is not None:
            params["include_software"] = int(include_software)
        if include_videos is not None:
            params["include_videos"] = int(include_videos)
        if include_hardware is not None:
            params["include_hardware"] = int(include_hardware)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetAppList/v1/",
            params=params,
            require_api_key=True,
        )

    @staticmethod
    def _normalize_app_entry(app: dict) -> dict:
        return {
            "app_id": app.get("appid"),
            "name": app.get("name") or "",
            "last_modified": app.get("last_modified"),
            "price_change_number": app.get("price_change_number"),
            "raw": app,
        }

    def get_app_list_summary(self, **kwargs) -> dict:
        payload = self.get_app_list(**kwargs)
        apps = payload.get("apps", [])
        return {
            "apps": [self._normalize_app_entry(app) for app in apps],
            "raw": payload,
        }

    def get_app_list_map(self, **kwargs) -> dict:
        apps = self.get_app_list_summary(**kwargs).get("apps", [])
        by_id = {
            str(app["app_id"]): app
            for app in apps
            if app.get("app_id") is not None
        }
        by_name = {
            app["name"]: app
            for app in apps
            if app.get("name")
        }
        return {
            "apps": apps,
            "count": len(apps),
            "apps_by_id": by_id,
            "apps_by_name": by_name,
        }

    def search_apps(
        self,
        query: str,
        *,
        max_results: int = 25,
        case_sensitive: bool = False,
        **kwargs,
    ) -> dict:
        normalized_query = ensure_not_blank(query, "query")
        comparison_query = normalized_query if case_sensitive else normalized_query.lower()
        entries = self.get_app_list_summary(**kwargs).get("apps", [])
        matches = []
        for app in entries:
            name = app.get("name", "")
            haystack = name if case_sensitive else name.lower()
            if comparison_query in haystack:
                matches.append(app)
            if len(matches) >= int(max_results):
                break
        return {
            "query": normalized_query,
            "matches": matches,
            "count": len(matches),
        }

    def find_app(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        exact: bool = False,
        prefer_exact: bool = True,
        **kwargs,
    ) -> dict:
        normalized_query = ensure_not_blank(query, "query")
        comparison_query = normalized_query if case_sensitive else normalized_query.lower()
        apps = self.get_app_list_summary(**kwargs).get("apps", [])

        exact_matches = []
        partial_matches = []
        for app in apps:
            name = app.get("name", "")
            haystack = name if case_sensitive else name.lower()
            if haystack == comparison_query:
                exact_matches.append(app)
            elif not exact and comparison_query in haystack:
                partial_matches.append(app)

        matches = exact_matches if exact or (prefer_exact and exact_matches) else exact_matches + partial_matches
        match = matches[0] if matches else None
        return {
            "query": normalized_query,
            "match": match,
            "matches": matches,
            "count": len(matches),
            "matched_exactly": bool(match and match in exact_matches),
        }
