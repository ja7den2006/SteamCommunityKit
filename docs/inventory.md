# Inventory

Inventory helpers do not require a Web API key. Public inventories can be read anonymously. Private inventories may require a logged-in session.

## Basic Inventory Read

```python
client = SteamClient()
payload = client.get_inventory_for_user("76561197960435530", 753, 6)
```

Convenience methods:

```python
client.get_inventory_items_for_user("76561197960435530", 753, 6)
client.get_inventory_items_summary_for_user("76561197960435530", 753, 6)
client.get_inventory_item_counts_for_user("76561197960435530", 753, 6)
```

## Full Pagination

```python
payload = client.get_full_inventory_for_user("76561197960435530", 753, 6, max_pages=2)
items = client.get_full_inventory_items_for_user("76561197960435530", 753, 6, max_pages=2)
summary = client.get_full_inventory_items_summary_for_user("76561197960435530", 753, 6, max_pages=2)
counts = client.get_full_inventory_item_counts_for_user("76561197960435530", 753, 6, max_pages=2)
```

## Find Inventory Items

```python
client.find_inventory_items_for_user(
    "76561197960435530",
    753,
    6,
    market_hash_name="Steam Trading Card",
)
```

Supported filters:

- `name_query`
- `market_hash_name`
- `tradable`
- `marketable`

## Asset Lookups

```python
client.get_inventory_item_by_asset_id_for_user("76561197960435530", 753, 6, "ASSET_ID")
client.get_full_inventory_item_by_asset_id_for_user("76561197960435530", 753, 6, "ASSET_ID")
```

## Inventory URLs

You can use full inventory URLs instead of separate IDs:

```python
url = "https://steamcommunity.com/inventory/76561197960435530/753/6"

client.get_inventory_by_url(url)
client.get_inventory_items_by_url(url)
client.get_inventory_items_summary_by_url(url)
client.get_inventory_item_counts_by_url(url)
client.find_inventory_items_by_url(url, tradable=True)
```

