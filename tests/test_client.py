import pytest

from steamcommunitykit import (
    CommunityCredentials,
    CredentialLoginResult,
    SteamAuthenticationError,
    SteamClient,
    SteamRateLimitError,
    SteamValidationError,
)
from steamcommunitykit.http import SteamHTTPTransport


class DummyResponse:
    def __init__(self, *, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON data configured")
        return self._json_data


class DummySession:
    def __init__(self, response):
        self.headers = {}
        self._response = response

    def request(self, **kwargs):
        return self._response

    def close(self):
        return None


class RecordingSession:
    def __init__(self, response):
        self.headers = {}
        self._response = response
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self._response

    def close(self):
        return None

    def post(self, url, timeout=None):
        self.calls.append({"method": "POST", "url": url, "timeout": timeout})
        return self._response


class SequenceSession:
    def __init__(self, responses):
        self.headers = {}
        self._responses = list(responses)
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)

    def close(self):
        return None


def test_transport_requires_api_key_for_protected_endpoint() -> None:
    transport = SteamHTTPTransport(session=DummySession(DummyResponse(json_data={"ok": True})))
    with pytest.raises(SteamAuthenticationError):
        transport.request("GET", "https://example.com", require_api_key=True)


def test_transport_unwraps_response_payload() -> None:
    transport = SteamHTTPTransport(
        api_key="test",
        session=DummySession(DummyResponse(json_data={"response": {"players": []}})),
    )
    assert transport.request("GET", "https://example.com", require_api_key=True) == {"players": []}


def test_client_exposes_expected_services() -> None:
    client = SteamClient(api_key="test")
    assert client.users is not None
    assert client.players is not None
    assert client.apps is not None
    assert client.store is not None
    assert client.published_files is not None
    assert client.published_item_search is not None
    assert client.published_item_voting is not None
    assert client.remote_storage is not None
    assert client.user_auth is not None
    assert client.webapi_util is not None
    assert client.workshop is not None
    assert client.community_api is not None
    client.close()


def test_community_credentials_build_cookie_from_access_token() -> None:
    credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        access_token="token123",
    )
    assert credentials.steam_login_secure_value == "76561197960435530%7C%7Ctoken123"


def test_users_service_publisher_endpoint_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"ownsapp": True}))
    client = SteamClient(api_key="test", session=session)

    client.users.check_app_ownership("76561197960435530", 440)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUser/CheckAppOwnership/v4/"
    assert call["params"]["steamid"] == "76561197960435530"
    assert call["params"]["appid"] == 440
    assert call["params"]["key"] == "test"
    client.close()


def test_apps_service_partner_list_method_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"applist": {}}))
    client = SteamClient(api_key="test", session=session)

    client.apps.get_partner_app_list_for_web_api_key("game,tool")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamApps/GetPartnerAppListForWebAPIKey/v2/"
    assert call["params"]["type_filter"] == "game,tool"
    assert call["params"]["key"] == "test"
    client.close()


def test_apps_service_get_app_betas_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"betas": []}))
    client = SteamClient(api_key="test", session=session)

    client.apps.get_app_betas(570)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamApps/GetAppBetas/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["key"] == "test"
    client.close()


def test_news_service_authed_method_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"appnews": {}}))
    client = SteamClient(api_key="test", session=session)

    client.news.get_news_for_app_authed(440, count=1)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamNews/GetNewsForAppAuthed/v2/"
    assert call["params"]["appid"] == 440
    assert call["params"]["count"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_transport_retries_rate_limited_response_until_success() -> None:
    session = SequenceSession(
        [
            DummyResponse(status_code=429, json_data={"error": "slow down"}, headers={"Retry-After": "0"}),
            DummyResponse(json_data={"response": {"ok": True}}, text="{}"),
        ]
    )
    transport = SteamHTTPTransport(api_key="test", session=session, backoff_factor=0, max_retries=1)

    result = transport.request("GET", "https://example.com", require_api_key=True)

    assert result == {"ok": True}
    assert len(session.calls) == 2


def test_transport_raises_rate_limit_error_after_exhausting_retries() -> None:
    session = SequenceSession(
        [
            DummyResponse(status_code=429, json_data={"error": "slow down"}, headers={"Retry-After": "0"}),
            DummyResponse(status_code=429, json_data={"error": "slow down"}, headers={"Retry-After": "0"}),
        ]
    )
    transport = SteamHTTPTransport(api_key="test", session=session, backoff_factor=0, max_retries=1)

    with pytest.raises(SteamRateLimitError):
        transport.request("GET", "https://example.com", require_api_key=True)


def test_get_app_price_info_rejects_more_than_100_app_ids() -> None:
    session = RecordingSession(DummyResponse(json_data={"price_info": {}}))
    client = SteamClient(api_key="test", session=session)

    with pytest.raises(SteamValidationError):
        client.users.get_app_price_info("76561197960435530", list(range(1, 102)))

    client.close()


def test_store_service_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"items": []}}))
    client = SteamClient(api_key="test", session=session)

    client.store.get_app_list(if_modified_since=1234567890, include_games=True)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IStoreService/GetAppList/v1/"
    assert call["params"]["if_modified_since"] == 1234567890
    assert call["params"]["include_games"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_published_files_query_uses_public_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"total": 0}}))
    client = SteamClient(api_key="test", session=session)

    client.published_files.query_files(query_type=0, cursor="*", app_id=570, total_only=True)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["totalonly"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_published_files_write_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)

    client.published_files.set_developer_metadata("123456", 570, "hello")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IPublishedFileService/SetDeveloperMetadata/v1/"
    assert call["data"]["publishedfileid"] == "123456"
    assert call["data"]["appid"] == 570
    assert call["data"]["metadata"] == "hello"
    client.close()


def test_remote_storage_public_details_use_public_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"publishedfiledetails": []}}))
    client = SteamClient(api_key="test", session=session)

    client.remote_storage.get_published_file_details(["123456", "789012"])

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    assert call["data"]["itemcount"] == 2
    assert call["data"]["publishedfileids[0]"] == "123456"
    assert call["data"]["publishedfileids[1]"] == "789012"
    client.close()


def test_remote_storage_subscribe_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"result": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.remote_storage.subscribe_published_file("76561197960435530", 570, "123456")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamRemoteStorage/SubscribePublishedFile/v1/"
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["appid"] == 570
    assert call["data"]["publishedfileid"] == "123456"
    assert call["params"]["key"] == "test"
    client.close()


def test_remote_storage_get_ugc_file_details_requires_app_id() -> None:
    session = RecordingSession(DummyResponse(json_data={"data": {"filename": "example"}}))
    client = SteamClient(api_key="test", session=session)

    client.remote_storage.get_ugc_file_details("123456", 570, "76561197960435530")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamRemoteStorage/GetUGCFileDetails/v1/"
    assert call["params"]["ugcid"] == "123456"
    assert call["params"]["appid"] == 570
    assert call["params"]["steamid"] == "76561197960435530"
    assert call["params"]["key"] == "test"
    client.close()


def test_remote_storage_set_ugc_used_by_gc_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.remote_storage.set_ugc_used_by_gc("76561197960435530", "123456", 570, True)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamRemoteStorage/SetUGCUsedByGC/v1/"
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["ugcid"] == "123456"
    assert call["data"]["appid"] == 570
    assert call["data"]["used"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_published_item_voting_uses_api_base_url_and_form_arrays() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"summary": []}}))
    client = SteamClient(api_key="test", session=session)

    client.published_item_voting.item_vote_summary("76561197960435530", 570, ["123456", "789012"])

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamPublishedItemVoting/ItemVoteSummary/v1/"
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["appid"] == 570
    assert call["data"]["count"] == 2
    assert call["data"]["publishedfileid[0]"] == "123456"
    assert call["data"]["publishedfileid[1]"] == "789012"
    assert call["params"]["key"] == "test"
    client.close()


def test_user_auth_ticket_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"steamid": "76561197960435530"}}))
    client = SteamClient(api_key="test", session=session)

    client.user_auth.authenticate_user_ticket(570, "abcdef", "server-1")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUserAuth/AuthenticateUserTicket/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["ticket"] == "abcdef"
    assert call["params"]["identity"] == "server-1"
    assert call["params"]["key"] == "test"
    client.close()


def test_user_auth_authenticate_user_hex_encodes_binary_inputs() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"token": "ok"}}))
    client = SteamClient(api_key="test", session=session)

    client.user_auth.authenticate_user(
        "76561197960435530",
        session_key=b"\xaa\xbb",
        encrypted_login_key=b"\x01\x02",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUserAuth/AuthenticateUser/v1/"
    assert call["data"]["sessionkey"] == "aabb"
    assert call["data"]["encrypted_loginkey"] == "0102"
    client.close()


def test_workshop_service_uses_input_json_on_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.workshop.set_item_payment_rules(
        570,
        99,
        associated_workshop_files=[{"publishedfileid": "123456"}],
        partner_accounts=[{"partner_account_id": 1, "percentage": 100}],
        make_workshop_files_subscribable=True,
        validate_only=True,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IWorkshopService/SetItemPaymentRules/v1/"
    assert call["params"]["key"] == "test"
    assert '"appid":570' in call["params"]["input_json"]
    assert '"gameitemid":99' in call["params"]["input_json"]
    assert '"validate_only":true' in call["params"]["input_json"]
    assert '"make_workshop_files_subscribable":true' in call["params"]["input_json"]
    client.close()


def test_workshop_get_item_daily_revenue_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"revenue": []}}))
    client = SteamClient(api_key="test", session=session)

    client.workshop.get_item_daily_revenue(570, 10, 0, 86400)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IWorkshopService/GetItemDailyRevenue/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["item_id"] == 10
    assert call["params"]["date_start"] == 0
    assert call["params"]["date_end"] == 86400
    assert call["params"]["key"] == "test"
    client.close()


def test_user_stats_set_user_stats_for_game_uses_indexed_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.user_stats.set_user_stats_for_game(
        "76561197960435530",
        570,
        {"kills_total": 5, "has_completed_tutorial": True},
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUserStats/SetUserStatsForGame/v1/"
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["appid"] == 570
    assert call["data"]["count"] == 2
    assert call["data"]["name[0]"] == "kills_total"
    assert call["data"]["value[0]"] == 5
    assert call["data"]["name[1]"] == "has_completed_tutorial"
    assert call["data"]["value[1]"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_community_api_report_abuse_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"eresult": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.community_api.report_abuse(
        "76561197960435530",
        "76561197972495328",
        570,
        1,
        2,
        "Test report",
        gid="1234567890",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamCommunity/ReportAbuse/v1/"
    assert call["data"]["steamidActor"] == "76561197960435530"
    assert call["data"]["steamidTarget"] == "76561197972495328"
    assert call["data"]["appid"] == 570
    assert call["data"]["abuseType"] == 1
    assert call["data"]["contentType"] == 2
    assert call["data"]["description"] == "Test report"
    assert call["data"]["gid"] == "1234567890"
    assert call["params"]["key"] == "test"
    client.close()


def test_published_item_search_uses_api_base_url_and_tag_arrays() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"results": []}}))
    client = SteamClient(api_key="test", session=session)

    client.published_item_search.ranked_by_trend(
        "76561197960435530",
        570,
        start_index=0,
        count=20,
        days=7,
        tags=["Maps", "Competitive"],
        user_tags=["Featured"],
        has_app_admin_access=True,
        file_type=0,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamPublishedItemSearch/RankedByTrend/v1/"
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["appid"] == 570
    assert call["data"]["startidx"] == 0
    assert call["data"]["count"] == 20
    assert call["data"]["days"] == 7
    assert call["data"]["tagcount"] == 2
    assert call["data"]["usertagcount"] == 1
    assert call["data"]["tag[0]"] == "Maps"
    assert call["data"]["tag[1]"] == "Competitive"
    assert call["data"]["usertag[0]"] == "Featured"
    assert call["data"]["hasappadminaccess"] == 1
    assert call["data"]["fileType"] == 0
    assert call["params"]["key"] == "test"
    client.close()


def test_webapi_util_get_supported_api_list_can_use_public_mode() -> None:
    session = RecordingSession(DummyResponse(json_data={"apilist": {"interfaces": []}}))
    client = SteamClient(api_key="test", session=session)

    client.webapi_util.get_supported_api_list()

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamWebAPIUtil/GetSupportedAPIList/v1/"
    assert call["params"]["format"] == "json"
    assert "key" not in call["params"]
    client.close()


def test_auth_build_qr_image_url_encodes_challenge_url() -> None:
    client = SteamClient(api_key="test")

    result = client.auth.build_qr_image_url("https://example.com/path?a=1&b=two")

    assert result.startswith("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=")
    assert "https%3A%2F%2Fexample.com%2Fpath%3Fa%3D1%26b%3Dtwo" in result
    client.close()


def test_auth_community_credentials_from_login_uses_cookie_response() -> None:
    response = DummyResponse(json_data={"response": {"ok": True}})
    response.cookies = {"sessionid": "session123", "steamLoginSecure": "securecookie123"}
    session = RecordingSession(response)
    client = SteamClient(api_key="test", session=session)

    login_result = CredentialLoginResult(
        steam_id="76561197960435530",
        account_name="tester",
        client_id=1,
        request_id="req",
        access_token="access123",
        refresh_token="refresh123",
    )

    original_set_cookie = client.auth.set_community_login_cookie

    def fake_set_cookie(**kwargs):
        return response

    client.auth.set_community_login_cookie = fake_set_cookie
    credentials = client.auth.community_credentials_from_login(login_result)
    client.auth.set_community_login_cookie = original_set_cookie

    assert credentials.session_id == "session123"
    assert credentials.steam_login_secure == "securecookie123"
    assert credentials.access_token == "access123"
    client.close()


def test_client_login_to_community_sets_credentials() -> None:
    client = SteamClient(api_key="test")

    login_result = CredentialLoginResult(
        steam_id="76561197960435530",
        account_name="tester",
        client_id=1,
        request_id="req",
        access_token="access123",
        refresh_token="refresh123",
    )
    expected_credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        steam_login_secure="securecookie123",
        access_token="access123",
    )

    original_login = client.auth.login_with_credentials
    original_build = client.auth.community_credentials_from_login

    client.auth.login_with_credentials = lambda *args, **kwargs: login_result
    client.auth.community_credentials_from_login = lambda result: expected_credentials

    returned = client.login_to_community("tester", "secret")

    client.auth.login_with_credentials = original_login
    client.auth.community_credentials_from_login = original_build

    assert returned is login_result
    assert client._transport.community_credentials == expected_credentials
    client.close()


def test_group_availability_uses_form_data_and_browser_headers() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<response><fieldId><![CDATA[groupName]]></fieldId>'
        '<bResults><![CDATA[1]]></bResults>'
        '<sResults><![CDATA[available]]></sResults></response>'
    )
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    result = client.groups.check_name_availability("examplegroupname")

    call = session.calls[0]
    assert result.available is True
    assert call["data"]["xml"] == "1"
    assert call["data"]["type"] == "groupName"
    assert call["headers"]["Content-Type"] == "application/x-www-form-urlencoded; charset=UTF-8"
    assert call["headers"]["Origin"] == "https://steamcommunity.com"
    assert call["headers"]["Referer"] == "https://steamcommunity.com/actions/GroupCreate"
    assert call["json"] is None
    client.close()


def test_group_availability_rate_limit_raises_specific_error() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<response><fieldId><![CDATA[groupName]]></fieldId>'
        '<bResults><![CDATA[]]></bResults>'
        '<sResults><![CDATA[You\'ve made too many requests recently. Please wait and try your request again later.]]></sResults></response>'
    )
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamRateLimitError):
        client.groups.check_name_availability("examplegroupname")

    client.close()


def test_create_group_raises_clear_error_for_account_restriction_page() -> None:
    error_html = """
    <html><body><div id="message"><h3>Your account does not meet the requirements to use this feature.</h3></div></body></html>
    """
    session = SequenceSession(
        [
            DummyResponse(text=error_html),
        ]
    )
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamAuthenticationError):
        client.groups.create_group(
            name="examplegroup",
            abbreviation="abc12",
            group_url="examplegroup",
            public=False,
            wait_for_sync=0,
            validate_availability=False,
        )

    client.close()


def test_create_group_can_skip_availability_checks() -> None:
    session = SequenceSession(
        [
            DummyResponse(json_data={}),
            DummyResponse(json_data={}),
        ]
    )
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    original_name = client.groups.check_name_availability
    original_tag = client.groups.check_tag_availability
    original_url = client.groups.check_url_availability
    original_fetch_id = client.groups.fetch_group_id
    original_fetch_id64 = client.groups.fetch_group_id64

    client.groups.check_name_availability = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("name availability should not be called")
    )
    client.groups.check_tag_availability = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("tag availability should not be called")
    )
    client.groups.check_url_availability = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("url availability should not be called")
    )
    client.groups.fetch_group_id = lambda _group_url: "1234"
    client.groups.fetch_group_id64 = lambda _group_url: "76561198000000000"

    created = client.groups.create_group(
        name="examplegroup",
        abbreviation="abc12",
        group_url="examplegroup",
        public=False,
        wait_for_sync=0,
        validate_availability=False,
    )

    client.groups.check_name_availability = original_name
    client.groups.check_tag_availability = original_tag
    client.groups.check_url_availability = original_url
    client.groups.fetch_group_id = original_fetch_id
    client.groups.fetch_group_id64 = original_fetch_id64

    assert created.group_id == "1234"
    assert created.group_id64 == "76561198000000000"
    assert len(session.calls) == 2
    client.close()
