from __future__ import annotations

from typing import Iterable, List, Union
from urllib.parse import urlencode

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamNotFoundError, SteamResponseError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id


STORE_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"


class AppsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamApps"

    def get_app_list(self) -> dict:
        raise SteamResponseError(
            "Steam no longer exposes a working public ISteamApps/GetAppList endpoint. "
            "Use store.get_app_list(...) with an API key, store.search_apps(...), or apps.get_app_details(app_id)."
        )

    def get_servers_at_address(self, address: str) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetServersAtAddress/v1/",
            params={"addr": address},
        )

    def up_to_date_check(self, app_id, version: int) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/UpToDateCheck/v1/",
            params={"appid": validate_app_id(app_id), "version": int(version)},
        )

    def get_app_details(
        self,
        app_id,
        *,
        language: str = "english",
        country: str = "US",
        filters: str = "",
    ) -> dict:
        normalized_app_id = validate_app_id(app_id)
        params = {
            "appids": normalized_app_id,
            "l": ensure_not_blank(language, "language"),
            "cc": ensure_not_blank(country, "country"),
        }
        if filters:
            params["filters"] = ensure_not_blank(filters, "filters")
        payload = self.transport.request(
            "GET",
            "{0}?{1}".format(STORE_APPDETAILS_URL, urlencode(params)),
        )
        app_payload = payload.get(str(normalized_app_id))
        if not isinstance(app_payload, dict):
            raise SteamResponseError("Steam did not return appdetails data for the requested app.")
        if not app_payload.get("success"):
            raise SteamNotFoundError(
                "Steam did not return app details for the requested app.",
                status_code=404,
                payload=app_payload,
            )
        data = app_payload.get("data") or {}
        genres = data.get("genres") or []
        categories = data.get("categories") or []
        screenshots = data.get("screenshots") or []
        movies = data.get("movies") or []
        release_date = data.get("release_date") or {}
        return {
            "app_id": data.get("steam_appid", normalized_app_id),
            "name": data.get("name") or "",
            "type": data.get("type") or "",
            "is_free": data.get("is_free"),
            "required_age": data.get("required_age"),
            "developers": data.get("developers") or [],
            "publishers": data.get("publishers") or [],
            "genres": [genre.get("description") for genre in genres if genre.get("description")],
            "categories": [category.get("description") for category in categories if category.get("description")],
            "short_description": data.get("short_description") or "",
            "header_image": data.get("header_image") or "",
            "website": data.get("website") or "",
            "screenshots": [shot.get("path_full") for shot in screenshots if shot.get("path_full")],
            "movies": [movie.get("mp4", {}).get("max") for movie in movies if movie.get("mp4", {}).get("max")],
            "release_date": release_date.get("date"),
            "coming_soon": release_date.get("coming_soon"),
            "supported_languages": data.get("supported_languages") or "",
            "raw": data,
        }

    def get_app_details_many(
        self,
        app_ids: Iterable[Union[str, int]],
        *,
        language: str = "english",
        country: str = "US",
        filters: str = "",
    ) -> List[dict]:
        results = []
        for app_id in app_ids:
            results.append(
                self.get_app_details(
                    app_id,
                    language=language,
                    country=country,
                    filters=filters,
                )
            )
        return results
