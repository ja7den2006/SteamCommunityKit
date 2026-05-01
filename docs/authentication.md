# Authentication

SteamCommunityKit supports three practical modes:

1. no key, no login
2. Steam Web API key
3. logged-in Steam Community session

## No Key

Use this for public community data:

- vanity resolution through community XML
- public profile XML reads
- market reads
- public inventory reads
- public group reads

```python
from steamcommunitykit import SteamClient

client = SteamClient()
print(client.resolve_steam_id("gaben"))
print(client.get_player_summary("gaben"))
```

## Steam Web API Key

Use a normal key from `https://steamcommunity.com/dev`.

```python
from steamcommunitykit import SteamClient

client = SteamClient(api_key="YOUR_WEB_API_KEY")
print(client.get_friend_list_for_user("gaben"))
print(client.get_owned_games_for_user("gaben"))
```

If a call needs a key and the client does not have one, the library raises:

- `SteamAuthenticationError: This endpoint requires a Steam Web API key.`

## Community Login

Use community login for account-backed flows:

- profile edits
- privacy writes
- avatar upload
- trade URL reads and rotation
- group availability checks
- group creation
- session reuse helpers

```python
from steamcommunitykit import SteamClient

client = SteamClient()
client.login_to_community("YOUR_USERNAME", "YOUR_PASSWORD")
print(client.get_account_info())
```

If Steam Guard is required and your script is running in an interactive terminal, `login_to_community(...)` prompts automatically.

If you already have the code, you can pass it directly:

```python
client.login_to_community(
    "YOUR_USERNAME",
    "YOUR_PASSWORD",
    steam_guard_code="12345",
)
```

Advanced callers can still provide their own code provider:

```python
client.login_to_community(
    "YOUR_USERNAME",
    "YOUR_PASSWORD",
    steam_guard_code_provider=lambda confirmation: get_code_somehow(confirmation),
)
```

## Refresh Token Login

```python
client = SteamClient()
client.login_to_community_with_refresh_token("YOUR_REFRESH_TOKEN")
```

## Session Export and Import

Cookie string:

```python
cookie_string = client.export_community_cookie_string()
client2 = SteamClient()
client2.set_community_credentials_from_cookie_string(cookie_string)
```

Cookie mapping:

```python
cookies = client.export_community_cookie_mapping()
client2.set_community_credentials_from_cookie_mapping(cookies)
```

JSON bundle:

```python
bundle_json = client.export_community_session_bundle_json()
client2.set_community_credentials_from_bundle_json(bundle_json)
```

Files:

```python
client.save_community_cookie_string("community_cookie.txt")
client.save_community_session_bundle("community_bundle.json")

restored = SteamClient()
restored.load_community_cookie_string("community_cookie.txt")
restored.load_community_session_bundle("community_bundle.json")
```

## Using Raw Requests With SteamCommunityKit Auth

```python
session = client.build_community_requests_session()
response = session.get("https://steamcommunity.com/my/edit/")
print(response.status_code)
```

This is useful when you need to hit a supported Steam Community page that does not yet have a first-class wrapper.

## Common Authentication Errors

- `SteamAuthenticationError`
  - missing Web API key
  - missing community credentials
  - limited-account or Family View restrictions
  - invalid login or incomplete auth flow

- `SteamValidationError`
  - malformed Steam IDs, URLs, or empty required input

- `SteamResponseError`
  - Steam returned malformed or unexpected content
