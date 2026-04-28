from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Union

import requests

from steamcommunitykit.constants import DEFAULT_TIMEOUT
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.models import CommunityCredentials, CredentialLoginResult
from steamcommunitykit.services import (
    AppsService,
    AuthenticationService,
    CommunityService,
    EconService,
    GroupsService,
    InventoryService,
    MarketService,
    NewsService,
    PlayersService,
    PublishedFilesService,
    RemoteStorageService,
    StoreService,
    UserStatsService,
    UsersService,
    WebAPIUtilService,
)
from steamcommunitykit.utils import load_api_key_from_json


class SteamClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        community_credentials: Optional[CommunityCredentials] = None,
    ) -> None:
        self._transport = SteamHTTPTransport(
            api_key=api_key,
            session=session,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            community_credentials=community_credentials,
        )
        self.users = UsersService(self._transport)
        self.players = PlayersService(self._transport)
        self.apps = AppsService(self._transport)
        self.news = NewsService(self._transport)
        self.user_stats = UserStatsService(self._transport)
        self.auth = AuthenticationService(self._transport)
        self.econ = EconService(self._transport)
        self.community = CommunityService(self._transport)
        self.groups = GroupsService(self._transport)
        self.inventory = InventoryService(self._transport)
        self.market = MarketService(self._transport)
        self.store = StoreService(self._transport)
        self.published_files = PublishedFilesService(self._transport)
        self.remote_storage = RemoteStorageService(self._transport)
        self.webapi_util = WebAPIUtilService(self._transport)

    @property
    def api_key(self) -> Optional[str]:
        return self._transport.api_key

    def set_api_key(self, api_key: str) -> None:
        self._transport.api_key = api_key

    def set_community_credentials(self, credentials: CommunityCredentials) -> None:
        self._transport.community_credentials = credentials

    def resolve_steam_id(self, identifier, url_type=None) -> str:
        return self.users.resolve_steam_id(identifier, url_type=url_type)

    def get_player_summary(self, identifier, url_type=None) -> dict:
        return self.users.get_player_summary(identifier, url_type=url_type)

    def get_player_summaries_map(self, identifiers, url_type=None) -> dict:
        if url_type is None:
            normalized = [self.resolve_steam_id(identifier) for identifier in identifiers]
        else:
            normalized = [self.resolve_steam_id(identifier, url_type=url_type) for identifier in identifiers]
        return self.users.get_player_summaries_map(normalized)

    def get_friend_list_for_user(self, identifier, relationship: str = "friend", url_type=None) -> dict:
        return self.users.get_friend_list(
            self.resolve_steam_id(identifier, url_type=url_type),
            relationship=relationship,
        )

    def get_friend_ids_for_user(self, identifier, relationship: str = "friend", url_type=None) -> list:
        return self.users.get_friend_ids(
            self.resolve_steam_id(identifier, url_type=url_type),
            relationship=relationship,
        )

    def get_friend_summaries_for_user(self, identifier, relationship: str = "friend", limit: int = None, url_type=None) -> dict:
        return self.users.get_friend_summaries(
            self.resolve_steam_id(identifier, url_type=url_type),
            relationship=relationship,
            limit=limit,
        )

    def get_user_group_list_for_user(self, identifier, url_type=None) -> dict:
        return self.users.get_user_group_list(
            self.resolve_steam_id(identifier, url_type=url_type),
        )

    def get_user_group_ids_for_user(self, identifier, url_type=None) -> list:
        return self.users.get_user_group_ids(
            self.resolve_steam_id(identifier, url_type=url_type),
        )

    def get_player_bans_summary(self, identifiers, url_type=None) -> list:
        if url_type is None:
            normalized = [self.resolve_steam_id(identifier) for identifier in identifiers]
        else:
            normalized = [self.resolve_steam_id(identifier, url_type=url_type) for identifier in identifiers]
        return self.users.get_player_bans_summary(normalized)

    def get_player_bans_map(self, identifiers, url_type=None) -> dict:
        if url_type is None:
            normalized = [self.resolve_steam_id(identifier) for identifier in identifiers]
        else:
            normalized = [self.resolve_steam_id(identifier, url_type=url_type) for identifier in identifiers]
        return self.users.get_player_bans_map(normalized)

    def get_owned_games_for_user(self, identifier, url_type=None, **kwargs) -> dict:
        return self.players.get_owned_games(
            self.resolve_steam_id(identifier, url_type=url_type),
            **kwargs,
        )

    def get_owned_games_summary_for_user(self, identifier, url_type=None, **kwargs) -> dict:
        return self.players.get_owned_games_summary(
            self.resolve_steam_id(identifier, url_type=url_type),
            **kwargs,
        )

    def get_recently_played_games_for_user(self, identifier, url_type=None, **kwargs) -> dict:
        return self.players.get_recently_played_games(
            self.resolve_steam_id(identifier, url_type=url_type),
            **kwargs,
        )

    def get_recently_played_games_summary_for_user(self, identifier, url_type=None, **kwargs) -> dict:
        return self.players.get_recently_played_games_summary(
            self.resolve_steam_id(identifier, url_type=url_type),
            **kwargs,
        )

    def get_single_game_playtime_for_user(self, identifier, app_id, url_type=None) -> dict:
        return self.players.get_single_game_playtime(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
        )

    def get_steam_level_for_user(self, identifier, url_type=None) -> dict:
        return self.players.get_steam_level(
            self.resolve_steam_id(identifier, url_type=url_type),
        )

    def get_badges_for_user(self, identifier, url_type=None) -> dict:
        return self.players.get_badges(
            self.resolve_steam_id(identifier, url_type=url_type),
        )

    def get_community_badge_progress_for_user(self, identifier, badge_id: int, url_type=None) -> dict:
        return self.players.get_community_badge_progress(
            self.resolve_steam_id(identifier, url_type=url_type),
            badge_id,
        )

    def get_group_id64(self, group_url: str) -> str:
        return self.groups.fetch_group_id64(group_url)

    def get_group_details(self, group_url: str, page: int = 1) -> dict:
        return self.groups.get_group_details(group_url, page=page)

    def get_group_members(self, group_url: str, page: int = 1) -> dict:
        return self.groups.get_group_members(group_url, page=page)

    def get_all_group_members(self, group_url: str, *, start_page: int = 1, max_pages: Optional[int] = None) -> dict:
        return self.groups.get_all_group_members(group_url, start_page=start_page, max_pages=max_pages)

    def get_group_member_summaries(self, group_url: str, *, page: int = 1, limit: Optional[int] = None) -> dict:
        return self.groups.get_group_member_summaries(group_url, page=page, limit=limit)

    def get_all_group_member_summaries(
        self,
        group_url: str,
        *,
        start_page: int = 1,
        max_pages: Optional[int] = None,
        max_members: Optional[int] = None,
    ) -> dict:
        return self.groups.get_all_group_member_summaries(
            group_url,
            start_page=start_page,
            max_pages=max_pages,
            max_members=max_members,
        )

    def get_published_file_detail(self, published_file_id) -> dict:
        return self.remote_storage.get_published_file_detail(published_file_id)

    def get_collection_detail(self, published_file_id) -> dict:
        return self.remote_storage.get_collection_detail(published_file_id)

    def get_collection_child_details(self, published_file_id) -> dict:
        return self.remote_storage.get_collection_child_details(published_file_id)

    def query_published_files(self, **kwargs) -> dict:
        return self.published_files.query_files_summary(**kwargs)

    def query_all_published_files(self, *, max_pages: Optional[int] = None, max_items: Optional[int] = None, **kwargs) -> dict:
        return self.published_files.query_all_files_summary(
            max_pages=max_pages,
            max_items=max_items,
            **kwargs,
        )

    def get_app_details(self, app_id, *, language: str = "english", country: str = "US", filters: str = "") -> dict:
        return self.apps.get_app_details(
            app_id,
            language=language,
            country=country,
            filters=filters,
        )

    def search_store_apps(self, query: str, *, max_results: int = 25, case_sensitive: bool = False, **kwargs) -> dict:
        return self.store.search_apps(
            query,
            max_results=max_results,
            case_sensitive=case_sensitive,
            **kwargs,
        )

    def get_news_summary(self, app_id, **kwargs) -> dict:
        return self.news.get_news_summary(app_id, **kwargs)

    def get_app_details_many(
        self,
        app_ids,
        *,
        language: str = "english",
        country: str = "US",
        filters: str = "",
    ) -> list:
        return self.apps.get_app_details_many(
            app_ids,
            language=language,
            country=country,
            filters=filters,
        )

    def get_global_achievement_percentages_map(self, app_id) -> dict:
        return self.user_stats.get_global_achievement_percentages_map(app_id)

    def get_player_achievements_summary_for_user(
        self,
        identifier,
        app_id,
        *,
        language: Optional[str] = None,
        url_type=None,
    ) -> dict:
        return self.user_stats.get_player_achievements_summary(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            language=language,
        )

    def get_inventory_for_user(
        self,
        identifier,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        url_type=None,
    ) -> dict:
        return self.inventory.get_inventory(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
        )

    def get_inventory_items_for_user(
        self,
        identifier,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        url_type=None,
    ) -> dict:
        return self.inventory.get_inventory_items(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
        )

    def get_inventory_items_summary_for_user(
        self,
        identifier,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        url_type=None,
    ) -> dict:
        return self.inventory.get_inventory_items_summary(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
        )

    def find_inventory_items_for_user(
        self,
        identifier,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        name_query: Optional[str] = None,
        market_hash_name: Optional[str] = None,
        tradable: Optional[bool] = None,
        marketable: Optional[bool] = None,
        url_type=None,
    ) -> dict:
        return self.inventory.find_inventory_items(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
            name_query=name_query,
            market_hash_name=market_hash_name,
            tradable=tradable,
            marketable=marketable,
        )

    def search_market_items(
        self,
        *,
        query: str = "",
        app_id=None,
        start: int = 0,
        count: int = 10,
        search_descriptions: bool = False,
        sort_column: str = "default",
        sort_dir: str = "desc",
    ) -> dict:
        return self.market.search_items_summary(
            query=query,
            app_id=app_id,
            start=start,
            count=count,
            search_descriptions=search_descriptions,
            sort_column=sort_column,
            sort_dir=sort_dir,
        )

    def get_market_item_listings_summary(
        self,
        app_id,
        market_hash_name: str,
        *,
        start: int = 0,
        count: int = 10,
        country: str = "US",
        language: str = "english",
        currency: int = 1,
    ) -> dict:
        return self.market.get_item_listings_summary(
            app_id,
            market_hash_name,
            start=start,
            count=count,
            country=country,
            language=language,
            currency=currency,
        )

    def search_all_market_items(
        self,
        *,
        query: str = "",
        app_id=None,
        start: int = 0,
        count: int = 10,
        search_descriptions: bool = False,
        sort_column: str = "default",
        sort_dir: str = "desc",
        max_pages: Optional[int] = None,
        max_results: Optional[int] = None,
    ) -> dict:
        return self.market.search_all_items(
            query=query,
            app_id=app_id,
            start=start,
            count=count,
            search_descriptions=search_descriptions,
            sort_column=sort_column,
            sort_dir=sort_dir,
            max_pages=max_pages,
            max_results=max_results,
        )

    def get_full_inventory_for_user(
        self,
        identifier,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        max_pages: Optional[int] = None,
        url_type=None,
    ) -> dict:
        return self.inventory.get_full_inventory(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
            max_pages=max_pages,
        )

    def get_full_inventory_items_for_user(
        self,
        identifier,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        max_pages: Optional[int] = None,
        url_type=None,
    ) -> dict:
        return self.inventory.get_full_inventory_items(
            self.resolve_steam_id(identifier, url_type=url_type),
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
            max_pages=max_pages,
        )

    def set_community_credentials_from_cookie_string(self, cookie_string: str) -> CommunityCredentials:
        credentials = self.auth.community_credentials_from_cookie_string(cookie_string)
        self.set_community_credentials(credentials)
        return credentials

    def login_to_community_with_refresh_token(self, refresh_token: str) -> CommunityCredentials:
        credentials = self.auth.community_credentials_from_refresh_token(refresh_token)
        self.set_community_credentials(credentials)
        return credentials

    def export_community_cookie_string(self) -> str:
        return self.auth.export_cookie_string(self._transport.require_community_credentials())

    def get_community_profile_bundle(self, steam_id=None) -> dict:
        return self.community.get_profile_bundle(steam_id)

    def get_web_api_key_page_state(self) -> dict:
        return self.community.get_web_api_key_page_state()

    def login_to_community(
        self,
        account_name: str,
        password: str,
        *,
        persistence: bool = True,
        steam_guard_code: Optional[str] = None,
        steam_guard_code_provider: Optional[Callable[[dict], str]] = None,
        prompt_for_steam_guard: bool = False,
        poll_interval: float = 1.5,
        poll_timeout: float = 60.0,
    ) -> CredentialLoginResult:
        login_result = self.auth.login_with_credentials(
            account_name,
            password,
            persistence=persistence,
            steam_guard_code=steam_guard_code,
            steam_guard_code_provider=steam_guard_code_provider,
            prompt_for_steam_guard=prompt_for_steam_guard,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )
        credentials = self.auth.community_credentials_from_login(login_result)
        self.set_community_credentials(credentials)
        return login_result

    @classmethod
    def from_api_json(
        cls,
        path: Union[str, Path],
        **kwargs,
    ) -> "SteamClient":
        return cls(api_key=load_api_key_from_json(path), **kwargs)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "SteamClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
