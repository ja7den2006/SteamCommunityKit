# Security Policy

## Supported Versions

Security fixes are applied to the latest public version on `main`.

## Sensitive Data

SteamCommunityKit can work with:

- Steam usernames and passwords
- Steam Guard codes
- Steam Web API keys
- refresh tokens
- `steamLoginSecure` cookies
- saved session bundle files

Treat all of those as secrets.

## Safe Usage Guidelines

- never commit session bundle files, cookie files, API keys, or credentials
- prefer test accounts when exercising profile writes or group flows
- rotate credentials if they are pasted into logs, terminals, or screenshots
- store exported session files outside version-controlled directories when possible

The provided `.gitignore` covers common local artifacts, but it cannot protect secrets that are deliberately committed.

## Reporting A Vulnerability

If you discover a security issue in this repository:

1. do not open a public issue with live credentials or exploit details
2. contact the maintainer privately first
3. include a minimal reproduction, affected version, and impact summary

## Scope Notes

This library intentionally supports account-backed community flows. That means the biggest security risk is usually operational misuse rather than a remote code execution class issue.

Focus first on:

- credential leakage
- cookie or refresh-token leakage
- unsafe persistence of exported session bundles
- missing validation around destructive account actions

