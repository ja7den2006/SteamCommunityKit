from __future__ import annotations

from steamcommunitykit.constants import COMMUNITY_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamNotFoundError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import normalize_uint64_ids, validate_app_id, validate_steam_id, validate_uint64


class RemoteStorageService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamRemoteStorage"

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

    @staticmethod
    def normalize_collection_detail(detail: dict) -> dict:
        children = detail.get("children") or []
        child_ids = [child.get("publishedfileid") for child in children if child.get("publishedfileid")]
        return {
            "published_file_id": detail.get("publishedfileid"),
            "result": detail.get("result"),
            "child_count": detail.get("childcount", len(child_ids)),
            "children": children,
            "child_ids": child_ids,
            "raw": detail,
        }

    @staticmethod
    def normalize_published_file_detail(detail: dict) -> dict:
        published_file_id = detail.get("publishedfileid")
        app_id = detail.get("consumer_appid") or detail.get("consumer_app_id")
        tags = detail.get("tags") or []
        previews = detail.get("previews") or []
        return {
            "published_file_id": published_file_id,
            "title": detail.get("title") or "",
            "description": detail.get("short_description") or "",
            "creator_steam_id": detail.get("creator"),
            "app_id": app_id,
            "app_name": detail.get("app_name") or "",
            "file_type": detail.get("file_type"),
            "visibility": detail.get("visibility"),
            "subscriptions": detail.get("subscriptions"),
            "favorites": detail.get("favorited"),
            "followers": detail.get("followers"),
            "views": detail.get("views"),
            "lifetime_subscriptions": detail.get("lifetime_subscriptions"),
            "lifetime_favorited": detail.get("lifetime_favorited"),
            "lifetime_followers": detail.get("lifetime_followers"),
            "time_created": detail.get("time_created"),
            "time_updated": detail.get("time_updated"),
            "preview_url": detail.get("preview_url") or "",
            "preview_urls": [preview.get("url") for preview in previews if preview.get("url")],
            "tags": [tag.get("tag") for tag in tags if tag.get("tag")],
            "tag_display_names": [tag.get("display_name") for tag in tags if tag.get("display_name")],
            "num_children": detail.get("num_children", 0),
            "children": detail.get("children", []),
            "can_subscribe": detail.get("can_subscribe"),
            "can_be_deleted": detail.get("can_be_deleted"),
            "banned": detail.get("banned"),
            "workshop_url": (
                "{0}/sharedfiles/filedetails/?id={1}".format(COMMUNITY_BASE_URL, published_file_id)
                if published_file_id
                else None
            ),
            "raw": detail,
        }

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

    def get_collection_details_summary(self, published_file_ids) -> dict:
        payload = self.get_collection_details(published_file_ids)
        details = payload.get("collectiondetails", [])
        normalized = [self.normalize_collection_detail(detail) for detail in details]
        return {
            "collections": normalized,
            "collection_ids": [detail.get("published_file_id") for detail in normalized if detail.get("published_file_id")],
            "raw": payload,
        }

    def get_collection_detail(self, published_file_id) -> dict:
        details = self.get_collection_details_summary([published_file_id]).get("collections", [])
        if not details:
            raise SteamNotFoundError(
                "Steam did not return a collection detail for the requested id.",
                status_code=404,
                payload={"published_file_id": str(published_file_id)},
            )
        first = details[0]
        if int(first.get("result", 0) or 0) != 1:
            raise SteamNotFoundError(
                "Steam did not return a valid collection detail for the requested id.",
                status_code=404,
                payload=first,
            )
        return first

    def get_collection_child_details(self, published_file_id) -> dict:
        collection = self.get_collection_detail(published_file_id)
        child_ids = collection.get("child_ids", [])
        children = []
        if child_ids:
            details = self.get_published_file_details(child_ids).get("publishedfiledetails", [])
            children = [
                self.normalize_published_file_detail(detail)
                for detail in details
                if int(detail.get("result", 0) or 0) == 1
            ]
        return {
            "collection": collection,
            "child_ids": child_ids,
            "children": children,
        }

    def get_published_file_detail(self, published_file_id) -> dict:
        detail = self.get_published_file_details([published_file_id]).get("publishedfiledetails", [])
        if not detail:
            raise SteamNotFoundError(
                "Steam did not return a published file detail for the requested id.",
                status_code=404,
                payload={"published_file_id": str(published_file_id)},
            )
        first = detail[0]
        if int(first.get("result", 0) or 0) != 1:
            raise SteamNotFoundError(
                "Steam did not return a valid published file detail for the requested id.",
                status_code=404,
                payload=first,
            )
        return self.normalize_published_file_detail(first)

    def get_ugc_file_details(self, ugc_id, app_id, steam_id=None) -> dict:
        params = {
            "ugcid": validate_uint64(ugc_id, "ugc_id"),
            "appid": validate_app_id(app_id),
        }
        if steam_id is not None:
            params["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetUGCFileDetails/v1/",
            params=params,
            require_api_key=True,
        )
