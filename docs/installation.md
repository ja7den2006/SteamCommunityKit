# Installation

## Install From GitHub

SteamCommunityKit is currently intended to be installed directly from the repository:

```bash
pip install git+https://github.com/ja7den2006/SteamCommunityKit.git
```

Install a specific branch or commit if needed:

```bash
pip install git+https://github.com/ja7den2006/SteamCommunityKit.git@main
```

## Install From A Local Checkout

```bash
git clone https://github.com/ja7den2006/SteamCommunityKit.git
cd SteamCommunityKit
pip install -e .[dev]
```

## Build Artifacts

To build a wheel and source distribution locally:

```bash
python -m build
```

This produces:

- `dist/steamcommunitykit-<version>.tar.gz`
- `dist/steamcommunitykit-<version>-py3-none-any.whl`

## Python Version

SteamCommunityKit currently targets Python `3.8+`.

## Dependencies

Runtime dependencies:

- `requests`
- `rsa`
- `PyJWT`

Development extras currently include:

- `pytest`
- `build`

## Sanity Check

After install:

```bash
python -c "from steamcommunitykit import SteamClient; print(SteamClient)"
```

