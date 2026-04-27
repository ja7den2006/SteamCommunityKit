from __future__ import annotations

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    normalize_uint64_ids,
    validate_app_id,
    validate_steam_id,
)


class PublishedItemVotingService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamPublishedItemVoting"

    def item_vote_summary(self, steam_id, app_id, published_file_ids) -> dict:
        normalized_ids = normalize_uint64_ids(published_file_ids, "published_file_id")
        data = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
            "count": len(normalized_ids),
        }
        for index, published_file_id in enumerate(normalized_ids):
            data["publishedfileid[{0}]".format(index)] = published_file_id
        return self.transport.request(
            "POST",
            f"{self.base_url}/ItemVoteSummary/v1/",
            data=data,
            require_api_key=True,
        )

    def user_vote_summary(self, steam_id, published_file_ids) -> dict:
        normalized_ids = normalize_uint64_ids(published_file_ids, "published_file_id")
        data = {
            "steamid": validate_steam_id(steam_id),
            "count": len(normalized_ids),
        }
        for index, published_file_id in enumerate(normalized_ids):
            data["publishedfileid[{0}]".format(index)] = published_file_id
        return self.transport.request(
            "POST",
            f"{self.base_url}/UserVoteSummary/v1/",
            data=data,
            require_api_key=True,
        )
