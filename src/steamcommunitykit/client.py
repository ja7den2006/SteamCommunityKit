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

    def get_friend_list_for_user(self, identifier, relationship: str = "friend", url_type=None) -> dict:
        return self.users.get_friend_list(
            self.resolve_steam_id(identifier, url_type=url_type),
            relationship=relationship,
        )

    def get_user_group_list_for_user(self, identifier, url_type=None) -> dict:
        return self.users.get_user_group_list(
            self.resolve_steam_id(identifier, url_type=url_type),
        )

    def get_owned_games_for_user(self, identifier, url_type=None, **kwargs) -> dict:
        return self.players.get_owned_games(
            self.resolve_steam_id(identifier, url_type=url_type),
            **kwargs,
        )

    def get_recently_played_games_for_user(self, identifier, url_type=None, **kwargs) -> dict:
        return self.players.get_recently_played_games(
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
