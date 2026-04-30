# Web API

These helpers use a normal Steam Web API key from `https://steamcommunity.com/dev`.

## Users

```python
client = SteamClient(api_key="YOUR_WEB_API_KEY")

client.resolve_steam_id("gaben")
client.get_player_summary("gaben")
client.get_player_summaries_map(["76561197960435530", "76561197968052866"])
client.get_friend_list_for_user("gaben")
client.get_friend_ids_for_user("gaben")
client.get_friend_summaries_for_user("gaben")
client.get_user_group_list_for_user("gaben")
client.get_user_group_ids_for_user("gaben")
client.get_friend_bans_for_user("gaben")
client.get_friend_bans_map_for_user("gaben")
```

## Player Data

```python
client.get_owned_games_for_user("gaben")
client.get_owned_games_summary_for_user("gaben")
client.find_owned_game_for_user("gaben", app_id=570)

client.get_recently_played_games_for_user("gaben")
client.get_recently_played_games_summary_for_user("gaben")
client.find_recently_played_game_for_user("gaben", app_id=570)

client.get_steam_level_for_user("gaben")
client.get_badges_for_user("gaben")
client.get_badges_summary_for_user("gaben")
client.get_community_badge_progress_for_user("gaben", badge_id=1)
client.get_community_badge_progress_summary_for_user("gaben", badge_id=1)
client.get_single_game_playtime_for_user("gaben", app_id=570)
```

## Apps and News

```python
client.get_app_details(570)
client.get_app_details_many([570, 730])
client.get_servers_at_address("127.0.0.1")
client.up_to_date_check(570, 0)

client.get_news_for_app(570, count=2)
client.get_news_summary(570, count=2)
```

## Stats

```python
client.get_number_of_current_players(570)
client.get_global_achievement_percentages_for_app(570)
client.get_global_achievement_percentages_map(570)
client.get_schema_for_game(570)
client.get_schema_for_game_summary(570)
client.get_global_stats_for_game(570, ["total_kills"])
client.get_global_stats_for_game_summary(570, ["total_kills"])
client.get_player_achievements_for_user("gaben", 570)
client.get_player_achievements_summary_for_user("gaben", 570)
client.get_user_stats_for_game_for_user("gaben", 570)
```

## Economy / Trade

These calls operate on the account tied to the Web API key.

```python
client.get_trade_offers_summary()
client.get_trade_offer_totals()
client.get_trade_offers()
client.get_trade_offers_summary_view()
client.get_trade_history()
client.get_trade_history_summary()
client.get_trade_offer_summary("TRADE_OFFER_ID")
```

## Store and Utility

```python
client.get_store_app_list()
client.get_store_app_list_summary()
client.get_store_app_list_map()
client.search_store_apps("Counter-Strike")
client.find_store_app("Counter-Strike")

client.get_web_api_server_info()
client.get_supported_api_list()
```

