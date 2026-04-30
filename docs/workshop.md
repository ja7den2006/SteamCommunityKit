# Workshop

Workshop helpers cover published file details, collection details, and query/search flows.

## Published File Details

```python
client = SteamClient(api_key="YOUR_WEB_API_KEY")

detail = client.get_published_file_detail("311707837")
details = client.get_published_file_details(["311707837", "2781880190"])
details_map = client.get_published_file_details_map(["311707837", "2781880190"])
```

By URL:

```python
client.get_published_file_detail_by_url(
    "https://steamcommunity.com/sharedfiles/filedetails/?id=311707837"
)
```

## Query Published Files

```python
payload = client.query_published_files(app_id=570, search_text="run")
print(payload["items"])
```

Cursor-based multi-page aggregation:

```python
payload = client.query_all_published_files(
    app_id=570,
    search_text="run",
    max_pages=2,
    max_items=10,
)
```

## Find A Specific Workshop Item

```python
payload = client.find_published_file(app_id=570, search_text="Dota Run Old")
print(payload["match"])
```

## Collections

```python
detail = client.get_collection_detail("3210489689")
children = client.get_collection_child_details("3210489689")
child_map = client.get_collection_child_map("3210489689")
match = client.find_collection_child("3210489689", "ChengHai3C test(?translating)")
```

By URL:

```python
url = "https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689"
client.get_collection_detail_by_url(url)
client.get_collection_child_details_by_url(url)
client.get_collection_child_map_by_url(url)
client.find_collection_child_by_url(url, "some title")
```

