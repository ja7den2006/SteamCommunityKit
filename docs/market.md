# Market

Market helpers do not require a Steam Web API key.

## Price Overview

```python
client = SteamClient()
payload = client.get_market_price_overview(730, "AK-47 | Redline (Field-Tested)")
print(payload["lowest_price"])
```

By full URL:

```python
client.get_market_price_overview_by_url(
    "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29"
)
```

## Search

```python
payload = client.search_market_items(730, "AK-47")
print(payload["total_count"])

match = client.find_market_item(730, "AK-47", market_hash_name="AK-47 | Redline (Field-Tested)")
print(match["match"])
```

## Listings

```python
summary = client.get_market_item_listings_summary(730, "AK-47 | Redline (Field-Tested)")
indexed = client.get_market_item_listings_map(730, "AK-47 | Redline (Field-Tested)")
listing = client.get_market_listing_by_id(730, "AK-47 | Redline (Field-Tested)", "LISTING_ID")
```

Multi-page:

```python
payload = client.get_all_market_item_listings_summary(
    730,
    "AK-47 | Redline (Field-Tested)",
    max_pages=2,
)
```

Filtered listing finders:

```python
payload = client.find_market_item_listings(
    730,
    "AK-47 | Redline (Field-Tested)",
    max_pages=2,
)
```

## Item Name ID and Order Book

```python
name_id = client.get_market_item_name_id(730, "AK-47 | Redline (Field-Tested)")
histogram = client.get_market_item_orders_histogram(730, "AK-47 | Redline (Field-Tested)")
summary = client.get_market_item_orders_summary(730, "AK-47 | Redline (Field-Tested)")
```

## Price History

```python
history = client.get_market_price_history(730, "AK-47 | Redline (Field-Tested)")
summary = client.get_market_price_history_summary(730, "AK-47 | Redline (Field-Tested)")
```

## One-Shot Market Snapshot

```python
snapshot = client.get_market_price_snapshot(730, "AK-47 | Redline (Field-Tested)")
print(snapshot["price_overview"])
print(snapshot["listing_summary"])
print(snapshot["orders_summary"])
```

