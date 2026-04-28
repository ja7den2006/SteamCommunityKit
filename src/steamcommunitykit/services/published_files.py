from __future__ import annotations

from typing import Dict, Optional, Sequence

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_uint64


class PublishedFilesService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IPublishedFileService"

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
