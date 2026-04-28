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
        self.cookies = {}

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


def test_client_exposes_expected_services() -> None:
    client = SteamClient(api_key="test")
    assert client.users is not None
    assert client.players is not None
    assert client.apps is not None
    assert client.news is not None
    assert client.user_stats is not None
    assert client.auth is not None
    assert client.econ is not None
    assert client.community is not None
    assert client.groups is not None
    assert client.store is not None
    assert client.published_files is not None
    assert client.remote_storage is not None
    assert client.webapi_util is not None
    assert not hasattr(client, "community_api")
    assert not hasattr(client, "published_item_search")
    assert not hasattr(client, "published_item_voting")
    assert not hasattr(client, "broadcast")
    assert not hasattr(client, "cheat_reporting")
    assert not hasattr(client, "cloud")
    assert not hasattr(client, "econ_market")
    assert not hasattr(client, "game_notifications")
    assert not hasattr(client, "leaderboards")
    assert not hasattr(client, "microtxn")
    assert not hasattr(client, "user_auth")
    assert not hasattr(client, "workshop")
    client.close()


def test_community_credentials_build_cookie_from_access_token() -> None:
    credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        access_token="token123",
    )
    assert credentials.steam_login_secure_value == "76561197960435530%7C%7Ctoken123"


def test_community_credentials_can_be_created_from_cookie_pair() -> None:
    credentials = CommunityCredentials.from_cookie_pair(
        session_id="session123",
        steam_login_secure="76561197960435530%7C%7Ctoken123",
    )

    assert credentials.steam_id == "76561197960435530"
    assert credentials.session_id == "session123"
    assert credentials.access_token == "token123"
    assert credentials.steam_login_secure == "76561197960435530%7C%7Ctoken123"


def test_users_service_uses_public_player_summaries_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"players": []}}))
    client = SteamClient(api_key="test", session=session)

    client.users.get_player_summaries("76561197960435530")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    assert call["params"]["steamids"] == "76561197960435530"
    assert call["params"]["key"] == "test"
    client.close()


def test_apps_service_uses_public_servers_at_address_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"servers": []}}))
    client = SteamClient(api_key="test", session=session)

    client.apps.get_servers_at_address("208.64.200.0")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamApps/GetServersAtAddress/v1/"
    assert call["params"]["addr"] == "208.64.200.0"
    assert "key" not in call["params"]
    client.close()


def test_news_service_authed_method_uses_public_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"appnews": {}}))
    client = SteamClient(api_key="test", session=session)

    client.news.get_news_for_app_authed(440, count=1)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamNews/GetNewsForAppAuthed/v2/"
    assert call["params"]["appid"] == 440
    assert call["params"]["count"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_store_service_uses_public_api_base_url() -> None:
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

    client.published_files.query_files(
        query_type=0,
        cursor="*",
        app_id=570,
        total_only=True,
        required_kv_tags=[{"key": "mode", "value": "ranked"}],
        return_metadata=True,
        return_playtime_stats=7,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["totalonly"] == 1
    assert call["params"]["return_metadata"] == 1
    assert call["params"]["return_playtime_stats"] == 7
    assert '"required_kv_tags":[{"key":"mode","value":"ranked"}]' in call["params"]["input_json"]
    assert call["params"]["key"] == "test"
    assert not hasattr(client.published_files, "set_developer_metadata")
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


def test_econ_get_trade_history_uses_user_key_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"trades": []}}))
    client = SteamClient(api_key="test", session=session)

    client.econ.get_trade_history(
        max_trades=50,
        start_after_time=0,
        start_after_trade_id="1234567890",
        navigating_back=False,
        get_descriptions=True,
        language="en",
        include_failed=False,
        include_total=True,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IEconService/GetTradeHistory/v1/"
    assert call["params"]["max_trades"] == 50
    assert call["params"]["start_after_time"] == 0
    assert call["params"]["start_after_tradeid"] == "1234567890"
    assert call["params"]["navigating_back"] == 0
    assert call["params"]["get_descriptions"] == 1
    assert call["params"]["language"] == "en"
    assert call["params"]["include_failed"] == 0
    assert call["params"]["include_total"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_econ_get_trade_offers_uses_user_key_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"trade_offers_sent": []}}))
    client = SteamClient(api_key="test", session=session)

    client.econ.get_trade_offers(
        get_sent_offers=True,
        get_received_offers=False,
        get_descriptions=True,
        language="en",
        active_only=True,
        historical_only=False,
        time_historical_cutoff=0,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IEconService/GetTradeOffers/v1/"
    assert call["params"]["get_sent_offers"] == 1
    assert call["params"]["get_received_offers"] == 0
    assert call["params"]["get_descriptions"] == 1
    assert call["params"]["language"] == "en"
    assert call["params"]["active_only"] == 1
    assert call["params"]["historical_only"] == 0
    assert call["params"]["time_historical_cutoff"] == 0
    assert call["params"]["key"] == "test"
    assert not hasattr(client.econ, "flush_inventory_cache")
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


def test_client_can_set_community_credentials_from_cookie_string() -> None:
    client = SteamClient(api_key="test")

    credentials = client.set_community_credentials_from_cookie_string(
        "sessionid=session123; steamLoginSecure=76561197960435530%7C%7Ctoken123"
    )

    assert credentials.steam_id == "76561197960435530"
    assert credentials.session_id == "session123"
    assert credentials.access_token == "token123"
    assert client._transport.community_credentials == credentials
    client.close()


def test_client_can_export_community_cookie_string() -> None:
    client = SteamClient(api_key="test")
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="76561197960435530%7C%7Ctoken123",
        )
    )

    cookie_string = client.export_community_cookie_string()

    assert cookie_string == "sessionid=session123; steamLoginSecure=76561197960435530%7C%7Ctoken123"
    client.close()


def test_client_can_login_with_refresh_token() -> None:
    client = SteamClient(api_key="test")
    expected_credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        steam_login_secure="76561197960435530%7C%7Ctoken123",
    )

    original_method = client.auth.community_credentials_from_refresh_token
    client.auth.community_credentials_from_refresh_token = lambda token: expected_credentials

    returned = client.login_to_community_with_refresh_token("refresh123")

    client.auth.community_credentials_from_refresh_token = original_method

    assert returned == expected_credentials
    assert client._transport.community_credentials == expected_credentials
    client.close()


def test_auth_can_build_community_credentials_from_refresh_token() -> None:
    response = DummyResponse(json_data={"response": {"ok": True}})
    response.cookies = {"steamLoginSecure": "76561197960435530%7C%7Ctoken123"}
    client = SteamClient(api_key="test")

    original_decode = client.auth.decode_jwt
    original_create_session = client.auth.create_session_id
    original_set_cookie = client.auth.set_community_login_cookie

    client.auth.decode_jwt = lambda token: {"sub": "76561197960435530"}
    client.auth.create_session_id = lambda: "session123"
    client.auth.set_community_login_cookie = lambda **kwargs: response

    credentials = client.auth.community_credentials_from_refresh_token("refresh123")

    client.auth.decode_jwt = original_decode
    client.auth.create_session_id = original_create_session
    client.auth.set_community_login_cookie = original_set_cookie

    assert credentials.steam_id == "76561197960435530"
    assert credentials.session_id == "session123"
    assert credentials.refresh_token == "refresh123"
    assert credentials.steam_login_secure == "76561197960435530%7C%7Ctoken123"
    client.close()


def test_community_edit_profile_posts_profile_save_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    client.community.edit_profile(
        persona_name="Example Name",
        summary="Example summary",
        custom_url="example-custom-url",
        country="US",
        state="FL",
        city=12345,
    )

    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/profiles/76561197960435530/edit/"
    assert call["data"]["sessionID"] == "session123"
    assert call["data"]["type"] == "profileSave"
    assert call["data"]["personaName"] == "Example Name"
    assert call["data"]["summary"] == "Example summary"
    assert call["data"]["customURL"] == "example-custom-url"
    assert call["data"]["country"] == "US"
    assert call["data"]["state"] == "FL"
    assert call["data"]["city"] == "12345"
    assert call["data"]["json"] == 1
    client.close()


def test_community_get_account_info_parses_embedded_json() -> None:
    html = """
    <div id="profile_edit_config"
         data-userinfo="{&quot;logged_in&quot;:true,&quot;steamid&quot;:&quot;76561197960435530&quot;,&quot;account_name&quot;:&quot;tester&quot;,&quot;is_limited&quot;:false}"
         data-profile-edit="{&quot;strPersonaName&quot;:&quot;Example&quot;,&quot;Privacy&quot;:{&quot;PrivacySettings&quot;:{&quot;PrivacyProfile&quot;:1},&quot;eCommentPermission&quot;:0}}"></div>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    info = client.community.get_account_info()

    assert info["logged_in"] is True
    assert info["steamid"] == "76561197960435530"
    assert info["account_name"] == "tester"
    assert info["is_limited"] is False
    client.close()


def test_community_get_profile_privacy_parses_embedded_json() -> None:
    html = """
    <div id="profile_edit_config"
         data-userinfo="{&quot;logged_in&quot;:true}"
         data-profile-edit="{&quot;strPersonaName&quot;:&quot;Example&quot;,&quot;Privacy&quot;:{&quot;PrivacySettings&quot;:{&quot;PrivacyProfile&quot;:1,&quot;PrivacyInventory&quot;:2},&quot;eCommentPermission&quot;:0}}"></div>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    privacy = client.community.get_profile_privacy()

    assert privacy["PrivacySettings"]["PrivacyProfile"] == 1
    assert privacy["PrivacySettings"]["PrivacyInventory"] == 2
    assert privacy["eCommentPermission"] == 0
    client.close()


def test_community_edit_profile_requires_at_least_one_field() -> None:
    client = SteamClient(api_key="test")
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamValidationError):
        client.community.edit_profile()

    client.close()


def test_groups_get_group_details_parses_memberslist_xml() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <memberList>
      <groupID64>103582791429521412</groupID64>
      <groupDetails>
        <groupName><![CDATA[Valve]]></groupName>
        <groupURL><![CDATA[Valve]]></groupURL>
        <headline><![CDATA[VALVE]]></headline>
        <summary><![CDATA[Test summary]]></summary>
        <avatarIcon><![CDATA[https://example.com/icon.jpg]]></avatarIcon>
        <avatarMedium><![CDATA[https://example.com/medium.jpg]]></avatarMedium>
        <avatarFull><![CDATA[https://example.com/full.jpg]]></avatarFull>
        <memberCount>152</memberCount>
        <membersInChat>53</membersInChat>
        <membersInGame>0</membersInGame>
        <membersOnline>67</membersOnline>
      </groupDetails>
      <memberCount>152</memberCount>
      <totalPages>3</totalPages>
      <currentPage>2</currentPage>
    </memberList>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)

    details = client.groups.get_group_details("Valve", page=2)

    assert details["group_id64"] == "103582791429521412"
    assert details["group_name"] == "Valve"
    assert details["group_url"] == "Valve"
    assert details["headline"] == "VALVE"
    assert details["summary"] == "Test summary"
    assert details["member_count"] == 152
    assert details["members_in_chat"] == 53
    assert details["members_in_game"] == 0
    assert details["members_online"] == 67
    assert details["total_pages"] == 3
    assert details["current_page"] == 2
    client.close()


def test_groups_get_group_members_parses_member_ids() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <memberList>
      <groupID64>103582791429521412</groupID64>
      <memberCount>152</memberCount>
      <totalPages>3</totalPages>
      <currentPage>1</currentPage>
      <members>
        <steamID64>76561197985607672</steamID64>
        <steamID64>76561197960435530</steamID64>
      </members>
    </memberList>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)

    members = client.groups.get_group_members("Valve", page=1)

    assert members["group_id64"] == "103582791429521412"
    assert members["member_count"] == 152
    assert members["total_pages"] == 3
    assert members["current_page"] == 1
    assert members["members"] == ["76561197985607672", "76561197960435530"]
    client.close()


def test_group_availability_uses_form_data_and_browser_headers() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<response><fieldId><![CDATA[groupName]]></fieldId>"
        "<bResults><![CDATA[1]]></bResults>"
        "<sResults><![CDATA[available]]></sResults></response>"
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
        "<response><fieldId><![CDATA[groupName]]></fieldId>"
        "<bResults><![CDATA[]]></bResults>"
        "<sResults><![CDATA[You've made too many requests recently. Please wait and try your request again later.]]></sResults></response>"
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
