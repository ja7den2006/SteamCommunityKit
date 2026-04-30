# Community

These helpers use a logged-in Steam Community session.

## Account and Profile Reads

```python
client.get_account_info()
client.get_profile_edit_state()
client.get_profile_privacy()
client.get_community_profile_bundle()
client.get_community_session_state()
```

`get_community_profile_bundle()` is the best one-shot read when you want account info, profile edit state, and privacy data from the same page load.

## Profile Edits

```python
client.edit_profile(
    persona_name="New Name",
    custom_url="mycustomslug",
    real_name="Jayden",
    summary="Profile summary text",
    country="US",
    state="IN",
    city="123",
)
```

Convenience wrappers:

```python
client.update_persona_name("New Name")
client.update_custom_url("mycustomslug")
client.update_real_name("Jayden")
client.update_summary("Profile summary text")
client.update_location(country="US", state="IN", city="123")
```

## Privacy

Read privacy:

```python
privacy = client.get_profile_privacy()
```

Write privacy:

```python
client.set_profile_privacy(
    privacy_profile=3,
    privacy_inventory=3,
    privacy_inventory_gifts=3,
    privacy_owned_games=3,
    privacy_playtime=3,
    privacy_friends_list=3,
    comment_permission=0,
)
```

Shortcuts:

```python
client.set_profile_public()
client.set_profile_private()
```

## Avatar Upload

```python
client.upload_avatar("avatar.png")
```

## Trade Offer URL

```python
trade_info = client.get_trade_offer_url()
print(trade_info["trade_url"])
print(trade_info["partner_steam_id"])
print(trade_info["token"])
```

Rotate the token:

```python
new_trade_info = client.rotate_trade_offer_url()
```

## Web API Key Page Helpers

These do not generate a key automatically. They help inspect the account state.

```python
client.get_web_api_key_status()
client.get_web_api_key_page_state()
```

Useful fields include:

- `has_access`
- `api_key`
- `domain`
- `registration_form_visible`
- `revoke_available`
- `reason`

