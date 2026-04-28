from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from steamcommunitykit import SteamClient, SteamError  # noqa: E402


DEFAULT_STEAM_ID = "76561197960435530"
DEFAULT_VANITY = "gaben"
DEFAULT_APP_ID = 570
DEFAULT_GROUP_URL = "valve"
DEFAULT_PUBLISHED_FILE_ID = "2682416130"
DEFAULT_GROUP_NAME_CHECK = "steamcommunitykit-smoke-check"


def print_header(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print("[{0}] {1}: {2}".format(status, name, detail))


def run_check(name: str, func) -> None:
    try:
        result = func()
        print_result(name, True, result)
    except Exception as exc:  # noqa: BLE001
        print_result(name, False, "{0}: {1}".format(type(exc).__name__, exc))


def build_client(args) -> SteamClient:
    if args.api_json:
        return SteamClient.from_api_json(args.api_json)
    if args.api_key:
        return SteamClient(api_key=args.api_key)
    raise ValueError("Provide either --api-json or --api-key.")


def configure_community_session(client: SteamClient, args) -> bool:
    if args.cookie_string:
        client.set_community_credentials_from_cookie_string(args.cookie_string)
        return True
    if args.refresh_token:
        client.login_to_community_with_refresh_token(args.refresh_token)
        return True
    if args.username and args.password:
        client.login_to_community(args.username, args.password)
        return True
    return False


def run_public_suite(client: SteamClient, args) -> None:
    print_header("Public / API Key Tests")

    run_check(
        "Resolve Steam ID From Vanity",
        lambda: client.resolve_steam_id(args.vanity),
    )
    run_check(
        "Get Player Summary",
        lambda: client.get_player_summary(args.profile_identifier).get("personaname", "<no personaname>"),
    )
    run_check(
        "Get Player Summaries Batch",
        lambda: "players={0}".format(
            len(client.users.get_player_summaries([args.steam_id, client.resolve_steam_id(args.vanity)]))
        ),
    )
    run_check(
        "Get Friend List",
        lambda: "friends={0}".format(
            len(client.get_friend_list_for_user(args.profile_identifier)["friendslist"]["friends"])
        ),
    )
    run_check(
        "Get User Group List",
        lambda: "groups={0}".format(
            len(client.get_user_group_list_for_user(args.profile_identifier).get("groups", []))
        ),
    )
    run_check(
        "Get Owned Games",
        lambda: _format_optional_count(
            client.get_owned_games_for_user(args.profile_identifier, include_appinfo=False),
            "game_count",
        ),
    )
    run_check(
        "Get Recently Played Games",
        lambda: _format_optional_count(
            client.get_recently_played_games_for_user(args.profile_identifier),
            "total_count",
        ),
    )
    run_check(
        "Get Steam Level",
        lambda: str(client.get_steam_level_for_user(args.profile_identifier).get("player_level", 0)),
    )
    run_check(
        "Get Badges",
        lambda: "badges={0}".format(len(client.get_badges_for_user(args.profile_identifier).get("badges", []))),
    )
    run_check(
        "Get Community Badge Progress",
        lambda: "quests={0}".format(
            len(client.get_community_badge_progress_for_user(args.profile_identifier, 1).get("quests", []))
        ),
    )
    run_check(
        "Get Servers At Address",
        lambda: "servers={0}".format(
            len(client.apps.get_servers_at_address("208.64.200.0").get("response", {}).get("servers", []))
        ),
    )
    run_check(
        "Up To Date Check",
        lambda: str(client.apps.up_to_date_check(args.app_id, 0).get("up_to_date")),
    )
    run_check(
        "Get News For App",
        lambda: "newsitems={0}".format(
            len(client.news.get_news_for_app(args.app_id, count=1).get("appnews", {}).get("newsitems", []))
        ),
    )
    run_check(
        "Get Number Of Current Players",
        lambda: str(client.user_stats.get_number_of_current_players(args.app_id).get("player_count", 0)),
    )
    run_check(
        "Get Global Achievement Percentages",
        lambda: "achievements={0}".format(
            len(
                client.user_stats.get_global_achievement_percentages_for_app(args.app_id).get(
                    "achievementpercentages", {}
                ).get("achievements", [])
            )
        ),
    )
    run_check(
        "Get Schema For Game",
        lambda: "gameName={0}".format(
            client.user_stats.get_schema_for_game(args.app_id).get("game", {}).get("gameName", "<unknown>")
        ),
    )
    run_check(
        "Get Global Stats For Game",
        lambda: "globalstats_keys={0}".format(
            sorted(
                client.user_stats.get_global_stats_for_game(
                    args.app_id,
                    ["total_kills"],
                ).keys()
            )
        ),
    )
    run_check(
        "Get Trade Offers Summary",
        lambda: "pending_received={0}".format(
            client.econ.get_trade_offers_summary().get("pending_received_count", 0)
        ),
    )
    run_check(
        "Get Trade Offers",
        lambda: "response_keys={0}".format(
            sorted(
                client.econ.get_trade_offers(
                    get_sent_offers=True,
                    get_received_offers=True,
                    get_descriptions=False,
                    language="en",
                    active_only=True,
                    historical_only=False,
                    time_historical_cutoff=0,
                ).keys()
            )
        ),
    )
    run_check(
        "Get Trade History",
        lambda: "response_keys={0}".format(
            sorted(
                client.econ.get_trade_history(
                    max_trades=10,
                    start_after_time=0,
                    start_after_trade_id="1",
                    navigating_back=False,
                    get_descriptions=False,
                    language="en",
                    include_failed=False,
                    include_total=True,
                ).keys()
            )
        ),
    )
    run_check(
        "Get Store App List",
        lambda: "apps={0}".format(
            len(client.store.get_app_list(include_games=True).get("apps", []))
        ),
    )
    run_check(
        "Query Published Files",
        lambda: "total={0}".format(
            client.published_files.query_files(
                query_type=0,
                app_id=args.app_id,
                cursor="*",
                num_per_page=1,
                total_only=True,
            ).get("total", 0)
        ),
    )
    run_check(
        "Get Published File Details",
        lambda: "details={0}".format(
            len(client.remote_storage.get_published_file_details([args.published_file_id]).get("publishedfiledetails", []))
        ),
    )
    run_check(
        "Get Collection Details",
        lambda: "collections={0}".format(
            len(client.remote_storage.get_collection_details([args.published_file_id]).get("collectiondetails", []))
        ),
    )
    run_check(
        "Get Web API Server Info",
        lambda: str(client.webapi_util.get_server_info()),
    )
    run_check(
        "Get Supported API List",
        lambda: "interfaces={0}".format(
            len(client.webapi_util.get_supported_api_list().get("apilist", {}).get("interfaces", []))
        ),
    )

    if args.include_conditional:
        print_header("Conditional / Steam-Dependent Public Tests")
        run_check(
            "Get Single Game Playtime",
            lambda: str(
                client.get_single_game_playtime_for_user(args.profile_identifier, args.app_id).get(
                    "playtime_forever", 0
                )
            ),
        )
        run_check(
            "Get News For App Authed",
            lambda: "newsitems={0}".format(
                len(
                    client.news.get_news_for_app_authed(args.app_id, count=1).get(
                        "appnews", {}
                    ).get("newsitems", [])
                )
            ),
        )
        run_check(
            "Get Player Achievements",
            lambda: "playerstats_keys={0}".format(
                sorted(
                    client.user_stats.get_player_achievements(
                        client.resolve_steam_id(args.profile_identifier),
                        args.app_id,
                    ).keys()
                )
            ),
        )
        run_check(
            "Get User Stats For Game",
            lambda: "playerstats_keys={0}".format(
                sorted(
                    client.user_stats.get_user_stats_for_game(
                        client.resolve_steam_id(args.profile_identifier),
                        args.app_id,
                    ).keys()
                )
            ),
        )
        run_check(
            "Get UGC File Details",
            lambda: "data_keys={0}".format(
                sorted(
                    client.remote_storage.get_ugc_file_details(
                        args.published_file_id,
                        args.app_id,
                        client.resolve_steam_id(args.profile_identifier),
                    ).keys()
                )
            ),
        )


def run_community_suite(client: SteamClient, args) -> None:
    print_header("Community / Logged-In Tests")

    run_check(
        "Get Account Info",
        lambda: str(client.community.get_account_info()),
    )
    run_check(
        "Get Profile Edit State",
        lambda: "persona={0}".format(client.community.get_profile_edit_state().get("strPersonaName", "")),
    )
    run_check(
        "Get Profile Privacy",
        lambda: str(client.community.get_profile_privacy()),
    )
    run_check(
        "Get Trade Offer URL",
        lambda: str(client.community.get_trade_offer_url()),
    )
    run_check(
        "Get Web API Key Status",
        lambda: str(client.community.get_web_api_key_status()),
    )
    run_check(
        "Check Group Name Availability",
        lambda: str(client.groups.check_name_availability(args.group_name_check)),
    )
    run_check(
        "Check Group URL Availability",
        lambda: str(client.groups.check_url_availability(args.group_name_check)),
    )
    run_check(
        "Check Group Tag Availability",
        lambda: str(client.groups.check_tag_availability(args.group_tag_check)),
    )
    run_check(
        "Get Group Details",
        lambda: str(client.groups.get_group_details(args.group_url)),
    )
    run_check(
        "Get Group Members",
        lambda: "members={0}".format(len(client.groups.get_group_members(args.group_url).get("members", []))),
    )

    if args.write_checks:
        run_check(
            "Write Check: Edit Profile With Current Persona",
            lambda: str(
                client.community.edit_profile(
                    persona_name=client.community.get_profile_edit_state().get("strPersonaName", "SteamCommunityKit")
                )
            ),
        )

    if args.rotate_trade_url:
        run_check(
            "Write Check: Rotate Trade URL",
            lambda: str(client.community.rotate_trade_offer_url()),
        )


def _format_optional_count(payload: dict, key: str) -> str:
    value = payload.get(key)
    if value is None:
        return "{0}=unavailable".format(key)
    return "{0}={1}".format(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SteamCommunityKit smoke test for both public API-key flows and logged-in community flows."
    )
    parser.add_argument("--api-json", type=Path, help="Path to api.json containing API_KEY.")
    parser.add_argument("--api-key", help="Steam Web API key.")
    parser.add_argument("--username", help="Steam username for community login.")
    parser.add_argument("--password", help="Steam password for community login.")
    parser.add_argument("--refresh-token", help="Steam refresh token for community login reuse.")
    parser.add_argument("--cookie-string", help="Community cookie string: sessionid=...; steamLoginSecure=...")
    parser.add_argument("--steam-id", default=DEFAULT_STEAM_ID, help="SteamID64 used for public API tests.")
    parser.add_argument(
        "--profile-identifier",
        default=DEFAULT_VANITY,
        help="SteamID64, vanity name, /profiles/... URL, or /id/... URL.",
    )
    parser.add_argument("--vanity", default=DEFAULT_VANITY, help="Vanity name used in resolution tests.")
    parser.add_argument("--app-id", type=int, default=DEFAULT_APP_ID, help="App ID used in game-related tests.")
    parser.add_argument(
        "--group-url",
        default=DEFAULT_GROUP_URL,
        help="Public group URL slug used for group read tests.",
    )
    parser.add_argument(
        "--published-file-id",
        default=DEFAULT_PUBLISHED_FILE_ID,
        help="Published file ID used for workshop/remote storage reads.",
    )
    parser.add_argument(
        "--group-name-check",
        default=DEFAULT_GROUP_NAME_CHECK,
        help="Name and URL slug used for group availability checks.",
    )
    parser.add_argument(
        "--group-tag-check",
        default="sckit1",
        help="Tag used for group abbreviation availability checks.",
    )
    parser.add_argument(
        "--community-only",
        action="store_true",
        help="Skip public API tests and only run community/session tests.",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Skip community/session tests even if login details are provided.",
    )
    parser.add_argument(
        "--write-checks",
        action="store_true",
        help="Run safe-ish write checks like profile edit using the current persona name.",
    )
    parser.add_argument(
        "--rotate-trade-url",
        action="store_true",
        help="Actually rotate the account's trade offer URL token.",
    )
    parser.add_argument(
        "--include-conditional",
        action="store_true",
        help="Include Steam-dependent checks that often fail due profile privacy or key restrictions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = build_client(args)
    try:
        if not args.community_only:
            run_public_suite(client, args)

        if not args.public_only:
            has_community_session = configure_community_session(client, args)
            if has_community_session:
                run_community_suite(client, args)
            else:
                print_header("Community / Logged-In Tests")
                print("Skipped community tests. Provide one of:")
                print("  --username + --password")
                print("  --refresh-token")
                print("  --cookie-string")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
