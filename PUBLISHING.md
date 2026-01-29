# Publishing to PyPI

Step-by-step guide to publishing and updating `yt-transcript-cli` on PyPI.

## Prerequisites

Install the build and upload tools:

```bash
pip install build twine
```

## First-time setup

1. Create an account at https://pypi.org/account/register/
2. Create an API token at https://pypi.org/manage/account/token/
   - Set the scope to "Entire account" for the first upload, or scope it to the project for subsequent uploads
3. Save the token somewhere secure (it starts with `pypi-`)

## Publishing a new version

### 1. Update the version number

Edit `pyproject.toml` and `src/yt_transcript/__init__.py` to set the new version:

```toml
# pyproject.toml
version = "0.2.0"
```

```python
# src/yt_transcript/__init__.py
__version__ = "0.2.0"
```

### 2. Clean previous builds

```bash
rm -rf dist/ build/ src/*.egg-info
```

### 3. Build the package

```bash
python -m build
```

This creates two files in `dist/`:
- `yt_transcript_cli-<version>.tar.gz` (source distribution)
- `yt_transcript_cli-<version>-py3-none-any.whl` (wheel)

### 4. Verify the build (optional but recommended)

```bash
twine check dist/*
```

### 5. Upload to PyPI

```bash
twine upload dist/*
```

When prompted:
- **Username:** `__token__`
- **Password:** your API token (the full string starting with `pypi-`)

### 6. Verify the upload

Visit https://pypi.org/project/yt-transcript-cli/ to confirm the package is live.

Test installation in a clean environment:

```bash
pip install yt-transcript-cli
```

## Updating an existing version

Repeat steps 1-6 above with a new version number. PyPI does not allow re-uploading the same version, so you must bump the version each time.

Follow [semantic versioning](https://semver.org/):
- **Patch** (0.1.0 -> 0.1.1): bug fixes
- **Minor** (0.1.0 -> 0.2.0): new features, backwards-compatible
- **Major** (0.1.0 -> 1.0.0): breaking changes

## Using a saved token

To avoid entering the token each time, create a `~/.pypirc` file:

```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
```

Or set an environment variable:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE
```

## Testing with TestPyPI (optional)

To test the upload without publishing to the real index:

```bash
twine upload --repository testpypi dist/*
```

Then install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ yt-transcript-cli
```

Register separately at https://test.pypi.org/account/register/ (it uses a different account/token).
