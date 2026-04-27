from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import requests

from steamcommunitykit.constants import DEFAULT_TIMEOUT
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.models import CommunityCredentials, CredentialLoginResult
from steamcommunitykit.services import (
    AppsService,
    AuthenticationService,
    CommunityAPIService,
    CommunityService,
    GroupsService,
    NewsService,
    PlayersService,
    PublishedFilesService,
    PublishedItemSearchService,
    PublishedItemVotingService,
    RemoteStorageService,
    StoreService,
    UserStatsService,
    UserAuthService,
    UsersService,
    WebAPIUtilService,
    WorkshopService,
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
        self.community_api = CommunityAPIService(self._transport)
        self.community = CommunityService(self._transport)
        self.groups = GroupsService(self._transport)
        self.store = StoreService(self._transport)
        self.published_files = PublishedFilesService(self._transport)
        self.published_item_search = PublishedItemSearchService(self._transport)
        self.published_item_voting = PublishedItemVotingService(self._transport)
        self.remote_storage = RemoteStorageService(self._transport)
        self.user_auth = UserAuthService(self._transport)
        self.webapi_util = WebAPIUtilService(self._transport)
        self.workshop = WorkshopService(self._transport)

    @property
    def api_key(self) -> Optional[str]:
        return self._transport.api_key

    def set_api_key(self, api_key: str) -> None:
        self._transport.api_key = api_key

    def set_community_credentials(self, credentials: CommunityCredentials) -> None:
        self._transport.community_credentials = credentials

    def login_to_community(
        self,
        account_name: str,
        password: str,
        *,
        persistence: bool = True,
    ) -> CredentialLoginResult:
        login_result = self.auth.login_with_credentials(
            account_name,
            password,
            persistence=persistence,
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
