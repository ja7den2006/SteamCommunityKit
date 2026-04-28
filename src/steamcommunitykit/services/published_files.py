from __future__ import annotations

from typing import Dict, Optional, Sequence

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint64


class PublishedFilesService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IPublishedFileService"

    def delete(self, published_file_id, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/Delete/v1/",
            params={
                "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
                "appid": validate_app_id(app_id),
            },
            require_api_key=True,
        )

    def query_files(
        self,
        *,
        query_type: int,
        page: int = 1,
        cursor: str = "*",
        creator_app_id: Optional[int] = None,
        app_id: Optional[int] = None,
        num_per_page: Optional[int] = None,
        required_tags: Optional[str] = None,
        excluded_tags: Optional[str] = None,
        match_all_tags: Optional[bool] = None,
        required_flags: Optional[str] = None,
        omitted_flags: Optional[str] = None,
        search_text: Optional[str] = None,
        file_type: Optional[int] = None,
        child_published_file_id=None,
        days: Optional[int] = None,
        include_recent_votes_only: Optional[bool] = None,
        cache_max_age_seconds: Optional[int] = None,
        language: Optional[int] = None,
        total_only: Optional[bool] = None,
        ids_only: Optional[bool] = None,
        return_vote_data: Optional[bool] = None,
        return_tags: Optional[bool] = None,
        return_kv_tags: Optional[bool] = None,
        return_previews: Optional[bool] = None,
        return_children: Optional[bool] = None,
        return_short_description: Optional[bool] = None,
        required_kv_tags: Optional[Sequence[Dict[str, str]]] = None,
        return_for_sale_data: Optional[bool] = None,
        return_metadata: Optional[bool] = None,
        return_playtime_stats: Optional[int] = None,
    ) -> dict:
        params = {
            "query_type": int(query_type),
            "page": int(page),
            "cursor": ensure_not_blank(cursor, "cursor"),
        }
        if creator_app_id is not None:
            params["creator_appid"] = validate_app_id(creator_app_id, "creator_app_id")
        if app_id is not None:
            params["appid"] = validate_app_id(app_id)
        if num_per_page is not None:
            params["numperpage"] = int(num_per_page)
        if required_tags:
            params["requiredtags"] = required_tags
        if excluded_tags:
            params["excludedtags"] = excluded_tags
        if match_all_tags is not None:
            params["match_all_tags"] = int(match_all_tags)
        if required_flags:
            params["required_flags"] = required_flags
        if omitted_flags:
            params["omitted_flags"] = omitted_flags
        if search_text:
            params["search_text"] = search_text
        if file_type is not None:
            params["filetype"] = int(file_type)
        if child_published_file_id is not None:
            params["child_publishedfileid"] = validate_uint64(
                child_published_file_id, "child_published_file_id"
            )
        if days is not None:
            params["days"] = int(days)
        if include_recent_votes_only is not None:
            params["include_recent_votes_only"] = int(include_recent_votes_only)
        if cache_max_age_seconds is not None:
            params["cache_max_age_seconds"] = int(cache_max_age_seconds)
        if language is not None:
            params["language"] = int(language)
        if total_only is not None:
            params["totalonly"] = int(total_only)
        if ids_only is not None:
            params["ids_only"] = int(ids_only)
        if return_vote_data is not None:
            params["return_vote_data"] = int(return_vote_data)
        if return_tags is not None:
            params["return_tags"] = int(return_tags)
        if return_kv_tags is not None:
            params["return_kv_tags"] = int(return_kv_tags)
        if return_previews is not None:
            params["return_previews"] = int(return_previews)
        if return_children is not None:
            params["return_children"] = int(return_children)
        if return_short_description is not None:
            params["return_short_description"] = int(return_short_description)
        if return_for_sale_data is not None:
            params["return_for_sale_data"] = int(return_for_sale_data)
        if return_metadata is not None:
            params["return_metadata"] = int(return_metadata)
        if return_playtime_stats is not None:
            params["return_playtime_stats"] = int(return_playtime_stats)
        service_payload = None
        if required_kv_tags is not None:
            service_payload = {"required_kv_tags": list(required_kv_tags)}
        return self.transport.request(
            "GET",
            f"{self.base_url}/QueryFiles/v1/",
            params=params,
            require_api_key=True,
            service_payload=service_payload,
        )

    def set_developer_metadata(self, published_file_id, app_id, metadata: str) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/SetDeveloperMetadata/v1/",
            require_api_key=True,
            service_payload={
                "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
                "appid": validate_app_id(app_id),
                "metadata": ensure_not_blank(metadata, "metadata"),
            },
        )

    def update_app_ugc_ban(
        self,
        steam_id,
        app_id,
        expiration_time: int,
        reason: Optional[str] = None,
    ) -> dict:
        data = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
            "expiration_time": int(expiration_time),
        }
        if reason:
            data["reason"] = reason
        return self.transport.request(
            "POST",
            f"{self.base_url}/UpdateAppUGCBan/v1/",
            require_api_key=True,
            service_payload=data,
        )

    def update_ban_status(
        self,
        published_file_id,
        app_id,
        banned: bool,
        reason: str,
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/UpdateBanStatus/v1/",
            require_api_key=True,
            service_payload={
                "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
                "appid": validate_app_id(app_id),
                "banned": int(banned),
                "reason": ensure_not_blank(reason, "reason"),
            },
        )

    def update_incompatible_status(self, published_file_id, app_id, incompatible: bool) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/UpdateIncompatibleStatus/v1/",
            require_api_key=True,
            service_payload={
                "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
                "appid": validate_app_id(app_id),
                "incompatible": int(incompatible),
            },
        )

    def update_tags(
        self,
        published_file_id,
        app_id,
        *,
        add_tags: Optional[str] = None,
        remove_tags: Optional[str] = None,
    ) -> dict:
        data = {
            "publishedfileid": validate_uint64(published_file_id, "published_file_id"),
            "appid": validate_app_id(app_id),
        }
        if add_tags:
            data["add_tags"] = add_tags
        if remove_tags:
            data["remove_tags"] = remove_tags
        return self.transport.request(
            "POST",
            f"{self.base_url}/UpdateTags/v1/",
            require_api_key=True,
            service_payload=data,
        )
