from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import PARTNER_API_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import normalize_uint64_ids, validate_app_id, validate_steam_id, validate_uint64


class RemoteStorageService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamRemoteStorage"
        self.partner_base_url = f"{PARTNER_API_BASE_URL}/ISteamRemoteStorage"

    def get_collection_details(self, published_file_ids) -> dict:
        normalized_ids = normalize_uint64_ids(published_file_ids, "published_file_id")
        data = {"collectioncount": len(normalized_ids)}
        for index, published_file_id in enumerate(normalized_ids):
            data["publishedfileids[{0}]".format(index)] = published_file_id
        return self.transport.request(
            "POST",
            f"{self.base_url}/GetCollectionDetails/v1/",
            data=data,
        )

    def get_published_file_details(self, published_file_ids) -> dict:
        normalized_ids = normalize_uint64_ids(published_file_ids, "published_file_id")
        data = {"itemcount": len(normalized_ids)}
        for index, published_file_id in enumerate(normalized_ids):
            data["publishedfileids[{0}]".format(index)] = published_file_id
        return self.transport.request(
            "POST",
            f"{self.base_url}/GetPublishedFileDetails/v1/",
            data=data,
        )

    def get_ugc_file_details(self, ugc_id, steam_id=None) -> dict:
        params = {"ugcid": validate_uint64(ugc_id, "ugc_id")}
        if steam_id is not None:
            params["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetUGCFileDetails/v1/",
            params=params,
            require_api_key=True,
        )

    def enumerate_user_subscribed_files(self, steam_id, app_id, list_type: Optional[int] = None) -> dict:
        data = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
        }
        if list_type is not None:
            data["listtype"] = int(list_type)
        return self.transport.request(
            "POST",
            f"{self.partner_base_url}/EnumerateUserSubscribedFiles/v1/",
            data=data,
            require_api_key=True,
        )

    def subscribe_published_file(self, steam_id, app_id, published_file_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.partner_base_url}/SubscribePublishedFile/v1/",
            data={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
                "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
            },
            require_api_key=True,
        )

    def unsubscribe_published_file(self, steam_id, app_id, published_file_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.partner_base_url}/UnsubscribePublishedFile/v1/",
            data={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
                "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
            },
            require_api_key=True,
        )
