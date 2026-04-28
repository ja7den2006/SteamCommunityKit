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
    assert client.broadcast is not None
    assert client.cheat_reporting is not None
    assert client.community_api is not None
    assert client.cloud is not None
    assert client.econ is not None
    assert client.game_notifications is not None
    assert client.leaderboards is not None
    assert client.microtxn is not None
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
    client.close()


def test_published_files_write_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)

    client.published_files.set_developer_metadata("123456", 570, "hello")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IPublishedFileService/SetDeveloperMetadata/v1/"
    assert '"publishedfileid":"123456"' in call["params"]["input_json"]
    assert '"appid":570' in call["params"]["input_json"]
    assert '"metadata":"hello"' in call["params"]["input_json"]
    assert call["params"]["key"] == "test"
    client.close()


def test_broadcast_service_uses_input_json_on_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.broadcast.post_game_data_frame(570, "76561197960435530", "123456", "{\"score\":42}")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IBroadcastService/PostGameDataFrame/v1/"
    assert call["params"]["key"] == "test"
    assert '"appid":570' in call["params"]["input_json"]
    assert '"steamid":"76561197960435530"' in call["params"]["input_json"]
    assert '"broadcast_id":"123456"' in call["params"]["input_json"]
    assert '"frame_data":"{\\"score\\":42}"' in call["params"]["input_json"]
    client.close()


def test_cheat_reporting_report_player_cheating_uses_service_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"reportid": "123"}}))
    client = SteamClient(api_key="test", session=session)

    client.cheat_reporting.report_player_cheating(
        "76561197972495328",
        570,
        reporter_steam_id="76561197960435530",
        app_data="7",
        heuristic=True,
        detection=False,
        player_report=True,
        no_report_id=False,
        game_mode=0,
        suspicion_start_time=0,
        severity=5,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ICheatReportingService/ReportPlayerCheating/v1/"
    assert call["params"]["key"] == "test"
    assert '"steamid":"76561197972495328"' in call["params"]["input_json"]
    assert '"appid":570' in call["params"]["input_json"]
    assert '"steamidreporter":"76561197960435530"' in call["params"]["input_json"]
    assert '"appdata":"7"' in call["params"]["input_json"]
    assert '"heuristic":true' in call["params"]["input_json"]
    assert '"detection":false' in call["params"]["input_json"]
    assert '"playerreport":true' in call["params"]["input_json"]
    assert '"noreportid":false' in call["params"]["input_json"]
    assert '"gamemode":0' in call["params"]["input_json"]
    assert '"suspicionstarttime":0' in call["params"]["input_json"]
    assert '"severity":5' in call["params"]["input_json"]
    client.close()


def test_cheat_reporting_get_cheating_reports_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"reports": []}}))
    client = SteamClient(api_key="test", session=session)

    client.cheat_reporting.get_cheating_reports(
        570,
        0,
        0,
        "0",
        include_reports=True,
        include_bans=False,
        steam_id="76561197972495328",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ICheatReportingService/GetCheatingReports/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["timeend"] == 0
    assert call["params"]["timebegin"] == 0
    assert call["params"]["reportidmin"] == "0"
    assert call["params"]["includereports"] == 1
    assert call["params"]["includebans"] == 0
    assert call["params"]["steamid"] == "76561197972495328"
    assert call["params"]["key"] == "test"
    client.close()


def test_cheat_reporting_request_vac_status_uses_service_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.cheat_reporting.request_vac_status_for_user(
        "76561197972495328",
        570,
        session_id="123456",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ICheatReportingService/RequestVacStatusForUser/v1/"
    assert call["params"]["key"] == "test"
    assert '"steamid":"76561197972495328"' in call["params"]["input_json"]
    assert '"appid":570' in call["params"]["input_json"]
    assert '"session_id":"123456"' in call["params"]["input_json"]
    client.close()


def test_microtxn_get_user_info_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"params": {"country": "US"}}}))
    client = SteamClient(api_key="test", session=session)

    client.microtxn.get_user_info(570, steam_id="76561197960435530")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamMicroTxn/GetUserInfo/v2/"
    assert call["params"]["appid"] == 570
    assert call["params"]["steamid"] == "76561197960435530"
    assert call["params"]["key"] == "test"
    client.close()


def test_microtxn_query_txn_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"result": "OK"}}))
    client = SteamClient(api_key="test", session=session)

    client.microtxn.query_txn(570, order_id="0", trans_id="123456")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamMicroTxn/QueryTxn/v3/"
    assert call["params"]["appid"] == 570
    assert call["params"]["orderid"] == "0"
    assert call["params"]["transid"] == "123456"
    assert call["params"]["key"] == "test"
    client.close()


def test_microtxn_get_report_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"result": "OK"}}))
    client = SteamClient(api_key="test", session=session)

    client.microtxn.get_report(
        570,
        "2026-01-01T00:00:00Z",
        report_type="GAMESALES",
        max_results=1000,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamMicroTxn/GetReport/v5/"
    assert call["params"]["appid"] == 570
    assert call["params"]["time"] == "2026-01-01T00:00:00Z"
    assert call["params"]["type"] == "GAMESALES"
    assert call["params"]["maxresults"] == 1000
    assert call["params"]["key"] == "test"
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


def test_cloud_enumerate_user_files_uses_access_token_params() -> None:
    session = RecordingSession(DummyResponse(json_data={"files": [], "total_files": 0}))
    client = SteamClient(api_key="test", session=session)

    client.cloud.enumerate_user_files(
        "token-123",
        570,
        extended_details=True,
        count=100,
        start_index=0,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ICloudService/EnumerateUserFiles/v1/"
    assert call["params"]["access_token"] == "token-123"
    assert call["params"]["appid"] == 570
    assert call["params"]["extended_details"] == 1
    assert call["params"]["count"] == 100
    assert call["params"]["start_index"] == 0
    assert "key" not in call["params"]
    client.close()


def test_cloud_begin_app_upload_batch_uses_input_json_form_body() -> None:
    session = RecordingSession(DummyResponse(json_data={"batch_id": "123"}))
    client = SteamClient(api_key="test", session=session)

    client.cloud.begin_app_upload_batch(
        "token-123",
        570,
        "Steam Deck",
        files_to_upload=["save1.sav"],
        files_to_delete=["save_old.sav"],
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ICloudService/BeginAppUploadBatch/v1/"
    assert call["data"]["access_token"] == "token-123"
    assert '"appid":570' in call["data"]["input_json"]
    assert '"machine_name":"Steam Deck"' in call["data"]["input_json"]
    assert '"files_to_upload":["save1.sav"]' in call["data"]["input_json"]
    assert '"files_to_delete":["save_old.sav"]' in call["data"]["input_json"]
    client.close()


def test_cloud_begin_http_upload_uses_input_json_form_body() -> None:
    session = RecordingSession(DummyResponse(json_data={"url_host": "example.com"}))
    client = SteamClient(api_key="test", session=session)

    client.cloud.begin_http_upload(
        "token-123",
        570,
        2048,
        "save1.sav",
        "0123456789abcdef0123456789abcdef01234567",
        "123456",
        platforms_to_sync=["all", "windows"],
        is_public=False,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ICloudService/BeginHTTPUpload/v1/"
    assert call["data"]["access_token"] == "token-123"
    assert '"file_size":2048' in call["data"]["input_json"]
    assert '"filename":"save1.sav"' in call["data"]["input_json"]
    assert '"file_sha":"0123456789abcdef0123456789abcdef01234567"' in call["data"]["input_json"]
    assert '"upload_batch_id":"123456"' in call["data"]["input_json"]
    assert '"platforms_to_sync":["all","windows"]' in call["data"]["input_json"]
    assert '"is_public":false' in call["data"]["input_json"]
    client.close()


def test_game_notifications_create_session_uses_service_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"sessionid": "123"}}))
    client = SteamClient(api_key="test", session=session)

    client.game_notifications.create_session(
        570,
        "match-1",
        "Competitive Match",
        [{"steamid": "76561197960435530"}],
        steam_id="76561197960435530",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IGameNotificationsService/CreateSession/v1/"
    assert call["params"]["key"] == "test"
    assert '"appid":570' in call["params"]["input_json"]
    assert '"context":"match-1"' in call["params"]["input_json"]
    assert '"title":"Competitive Match"' in call["params"]["input_json"]
    assert '"users":[{"steamid":"76561197960435530"}]' in call["params"]["input_json"]
    assert '"steamid":"76561197960435530"' in call["params"]["input_json"]
    client.close()


def test_game_notifications_enumerate_sessions_uses_get_service_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"sessions": []}}))
    client = SteamClient(api_key="test", session=session)

    client.game_notifications.enumerate_sessions_for_app(
        570,
        "76561197960435530",
        include_all_user_messages=True,
        include_auth_user_message=False,
        language="en",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IGameNotificationsService/EnumerateSessionsForApp/v1/"
    assert call["params"]["key"] == "test"
    assert '"appid":570' in call["params"]["input_json"]
    assert '"steamid":"76561197960435530"' in call["params"]["input_json"]
    assert '"include_all_user_messages":true' in call["params"]["input_json"]
    assert '"include_auth_user_message":false' in call["params"]["input_json"]
    assert '"language":"en"' in call["params"]["input_json"]
    client.close()


def test_game_notifications_delete_session_batch_uses_session_id_list() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.game_notifications.delete_session_batch(570, ["123", 456])

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IGameNotificationsService/DeleteSessionBatch/v1/"
    assert call["params"]["key"] == "test"
    assert '"appid":570' in call["params"]["input_json"]
    assert '"sessionids":["123","456"]' in call["params"]["input_json"]
    client.close()


def test_econ_get_trade_history_uses_api_base_url() -> None:
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


def test_econ_get_trade_offers_uses_api_base_url() -> None:
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
    client.close()


def test_econ_flush_inventory_cache_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"success": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.econ.flush_inventory_cache("76561197960435530", 730, "2")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IEconService/FlushInventoryCache/v1/"
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["appid"] == 730
    assert call["data"]["contextid"] == "2"
    assert call["params"]["key"] == "test"
    client.close()


def test_leaderboards_find_or_create_uses_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"leaderboardid": 1}}))
    client = SteamClient(api_key="test", session=session)

    client.leaderboards.find_or_create_leaderboard(
        570,
        "BestTimes",
        sort_method="Ascending",
        display_type="TimeSeconds",
        create_if_not_found=True,
        only_trusted_writes=True,
        only_friends_reads=False,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamLeaderboards/FindOrCreateLeaderboard/v2/"
    assert call["data"]["appid"] == 570
    assert call["data"]["name"] == "BestTimes"
    assert call["data"]["sortmethod"] == "Ascending"
    assert call["data"]["displaytype"] == "TimeSeconds"
    assert call["data"]["createifnotfound"] == 1
    assert call["data"]["onlytrustedwrites"] == 1
    assert call["data"]["onlyfriendsreads"] == 0
    assert call["params"]["key"] == "test"
    client.close()


def test_leaderboards_get_entries_uses_signed_ranges() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"entries": []}}))
    client = SteamClient(api_key="test", session=session)

    client.leaderboards.get_leaderboard_entries(
        570,
        123,
        -5,
        5,
        "RequestAroundUser",
        steam_id="76561197960435530",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamLeaderboards/GetLeaderboardEntries/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["leaderboardid"] == 123
    assert call["params"]["rangestart"] == -5
    assert call["params"]["rangeend"] == 5
    assert call["params"]["datarequest"] == "RequestAroundUser"
    assert call["params"]["steamid"] == "76561197960435530"
    assert call["params"]["key"] == "test"
    client.close()


def test_leaderboards_set_score_hex_encodes_details() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"score_changed": True}}))
    client = SteamClient(api_key="test", session=session)

    client.leaderboards.set_leaderboard_score(
        570,
        123,
        "76561197960435530",
        999,
        "KeepBest",
        details=b"\x00\xff",
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamLeaderboards/SetLeaderboardScore/v1/"
    assert call["data"]["appid"] == 570
    assert call["data"]["leaderboardid"] == 123
    assert call["data"]["steamid"] == "76561197960435530"
    assert call["data"]["score"] == 999
    assert call["data"]["scoremethod"] == "KeepBest"
    assert call["data"]["details"] == "00ff"
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
