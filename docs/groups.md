# Groups

SteamCommunityKit supports both public group reads and logged-in group actions.

## Public Reads

```python
client = SteamClient()

details = client.get_group_details("Valve")
members = client.get_group_members("Valve")
group_id64 = client.get_group_id64("Valve")
```

Aggregate across pages:

```python
payload = client.get_all_group_members("steamdb", max_pages=2)
print(payload["pages_fetched"])
print(len(payload["members"]))
```

## Group Member Summaries

With a Web API key:

```python
client = SteamClient(api_key="YOUR_WEB_API_KEY")

payload = client.get_group_member_summaries("Valve", limit=5)
indexed = client.get_group_member_summaries_map("Valve", limit=5)
```

## Availability Checks

Logged-in community session required:

```python
client.check_group_name_availability("my-group-name")
client.check_group_url_availability("my-group-url")
client.check_group_tag_availability("TAG")
```

## Membership State

Logged-in community session required:

```python
state = client.get_group_membership_state("Valve")
print(state["membership_state"])
print(state["can_join"])
print(state["can_leave"])
print(state["group_id"])
```

This is a read-only helper that parses the current group page for the logged-in account.

## Group Creation

```python
created = client.create_group(
    name="My SteamCommunityKit Group",
    abbreviation="SCKIT",
    group_url="my-steamcommunitykit-group",
    public=True,
)
print(created.group_id64)
```

Steam may block this when:

- the account is limited
- Family View is active
- the name, URL, or tag is unavailable
- Steam rate-limits group validation

The library surfaces those failures through explicit exceptions instead of vague booleans.

