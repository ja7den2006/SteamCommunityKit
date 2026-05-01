# SteamCommunityKit

`SteamCommunityKit` is a Python library for real Steam user workflows:

- public Steam Web API reads with a normal `steamcommunity.com/dev` key
- public no-key community reads such as profile XML, market data, inventory URLs, and group URLs
- logged-in Steam Community actions such as profile edits, privacy updates, avatar upload, trade URL management, and group creation checks
- session persistence helpers for refresh tokens, cookies, JSON bundles, and external `requests.Session` reuse

This package is built around the workflows normal users can actually use. It does not try to wrap Steamworks publisher-only administration endpoints that require partner permissions.

## Install

Install from GitHub:

```bash
pip install git+https://github.com/ja7den2006/SteamCommunityKit.git
```

Install from a local checkout:

```bash
pip install -e .[dev]
```

## Choose The Right Mode

Use no key when you only need public community data:

```python
from steamcommunitykit import SteamClient

client = SteamClient()
print(client.resolve_steam_id("gaben"))
print(client.get_player_summary("https://steamcommunity.com/id/gaben/"))
print(client.get_market_price_overview(730, "AK-47 | Redline (Field-Tested)"))
```

Use a normal Steam Web API key when you need Web API calls:

```python
from steamcommunitykit import SteamClient

client = SteamClient(api_key="YOUR_WEB_API_KEY")
summary = client.get_player_summary("gaben")
games = client.get_owned_games_for_user("https://steamcommunity.com/id/gaben/")
news = client.get_news_summary(570, count=2)

print(summary["personaname"])
print(games["game_count"])
print(news["items"][0]["title"])
```

Use community login when you need account-backed actions:

```python
from steamcommunitykit import SteamClient

client = SteamClient()
client.login_to_community("YOUR_USERNAME", "YOUR_PASSWORD")

print(client.get_account_info())
print(client.get_trade_offer_url())
print(client.get_group_membership_state("Valve"))
```

If Steam Guard is required, the credential login flow prompts automatically in an interactive terminal. You can still pass `steam_guard_code="12345"` explicitly for non-interactive runs.

## Verified Workflow Examples

### Save and restore a logged-in session

```python
from steamcommunitykit import SteamClient

client = SteamClient()
client.login_to_community("YOUR_USERNAME", "YOUR_PASSWORD")
client.save_community_session_bundle("steam_session.json")

restored = SteamClient()
restored.load_community_session_bundle("steam_session.json")
print(restored.get_community_session_state())
```

### Reuse Steam Community auth with raw requests

```python
from steamcommunitykit import SteamClient

client = SteamClient()
client.login_to_community("YOUR_USERNAME", "YOUR_PASSWORD")

session = client.build_community_requests_session()
response = session.get("https://steamcommunity.com/my/edit/")
print(response.status_code)
```

### Market snapshot from a full listing URL

```python
from steamcommunitykit import SteamClient

client = SteamClient()
snapshot = client.get_market_price_snapshot_by_url(
    "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29"
)
print(snapshot["price_overview"]["lowest_price"])
print(snapshot["listing_summary"]["listing_count"])
```

## Major Features

### Authentication and session management

- credential login with Steam Guard support
- refresh-token login reuse
- cookie string, cookie mapping, and JSON bundle import/export
- file-based session save/load helpers
- ready-to-use authenticated `requests.Session`

### Community account features

- account/profile bundle reads
- profile edits for persona name, vanity URL, summary, real name, and location
- privacy reads and writes
- avatar upload
- trade offer URL read/rotate
- Web API key status page parsing

### Groups

- name, URL, and tag availability checks
- group details, members, and multi-page member aggregation
- group member summaries and indexed maps
- group membership state parsing for the logged-in account
- group creation with validation and clear limited-account errors

### Market

- search, normalized results, and exact-match helpers
- price overview
- listing summaries, maps, filtered lookups, and multi-page aggregation
- item name ID, order histogram, order summary, and price history
- one-shot market snapshots
- full URL-based helper variants

### Inventory

- raw and normalized inventory reads
- full pagination helpers
- item search/filtering
- item counts, asset ID lookup, and URL-based inventory helpers

### Workshop and collections

- published file detail helpers
- collection details and child item helpers
- query helpers with cursor pagination
- normalized maps and exact-match finders
- full workshop URL helper variants

### Web API reads

- users, friends, bans, owned games, recently played games, badges, levels
- apps, news, user stats, trade/econ summaries, store searches, and utility endpoints

## Documentation

- [Installation Guide](docs/installation.md)
- [Authentication Guide](docs/authentication.md)
- [Community Guide](docs/community.md)
- [Groups Guide](docs/groups.md)
- [Market Guide](docs/market.md)
- [Inventory Guide](docs/inventory.md)
- [Workshop Guide](docs/workshop.md)
- [Web API Guide](docs/webapi.md)
- [Testing Guide](docs/testing.md)
- [Security Policy](SECURITY.md)

## Testing

Run the unit suite:

```bash
python -m pytest -q
```

Run the public smoke suite with an API key:

```bash
python examples/smoke_test.py --api-key YOUR_WEB_API_KEY --public-only
```

Run the community smoke suite with a Steam account:

```bash
python examples/smoke_test.py --username YOUR_USERNAME --password YOUR_PASSWORD --community-only
```

## Notes

- Some Web API features require a normal Steam Web API key.
- Some community features require a logged-in session.
- Some actions are restricted by Steam account state, such as limited accounts, Family View, or profile privacy.
- When a feature requires more auth than the current client state provides, the package raises explicit `SteamAuthenticationError` or `SteamValidationError` messages instead of failing silently.

## Disclaimer

This project is not affiliated with Valve or Steam. Steam pages and response shapes can change over time, so some community-backed helpers may need maintenance if Steam updates its HTML or request flows.
