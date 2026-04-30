# Testing

SteamCommunityKit ships with both unit tests and a live smoke script.

## Unit Tests

```bash
python -m pytest -q
```

## Public Smoke With A Web API Key

```bash
python examples/smoke_test.py --api-key YOUR_WEB_API_KEY --public-only
```

Or with a local `api.json`:

```bash
python examples/smoke_test.py --api-json path\\to\\api.json --public-only
```

## Public Smoke Without A Key

```bash
python examples/smoke_test.py --public-only
```

This exercises public community features such as:

- vanity resolution
- community profile XML
- market search, pricing, listings, and snapshots
- public group reads

## Community Smoke With A Logged-In Account

```bash
python examples/smoke_test.py --username YOUR_USERNAME --password YOUR_PASSWORD --community-only
```

This exercises account-backed features such as:

- profile bundle reads
- privacy reads
- trade offer URL parsing
- Web API key page state
- group membership state
- session roundtrips
- inventory helpers

## Optional Write Checks

```bash
python examples/smoke_test.py --username YOUR_USERNAME --password YOUR_PASSWORD --community-only --write-checks
```

Optional flags already supported by the smoke script include:

- `--steam-guard-code`
- `--rotate-trade-url`
- `--set-persona-name`
- `--set-custom-url`
- `--set-real-name`
- `--set-summary`
- `--avatar-image`
- `--editable-group-url`

## Notes

- Some checks are expected to be blocked by Steam account state, such as limited-account restrictions.
- That is still a valid test if the library reports the failure clearly.
- Do not use your main account for destructive write checks unless you intend to change real account state.

