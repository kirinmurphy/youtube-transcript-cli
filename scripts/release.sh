#!/usr/bin/env bash

set -Eeuo pipefail

PACKAGE_NAME="yt-transcript-cli"
PYPI_JSON_URL="https://pypi.org/pypi/${PACKAGE_NAME}/json"

usage() {
    cat <<'EOF'
Usage: ./scripts/release.sh VERSION [--yes] [--skip-install]

Build, publish, and reinstall a new yt-transcript-cli release.

Arguments:
  VERSION         New semantic version, for example 0.2.0

Options:
  --yes           Skip the release confirmation
  --skip-install  Do not reinstall the published package with pipx
  -h, --help      Show this help

Examples:
  ./scripts/release.sh 0.2.0
  ./scripts/release.sh 0.2.1 --yes
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

select_python() {
    local candidate
    local candidates=(
        "${PYTHON_BIN:-}"
        python3
        python3.15
        python3.14
        python3.13
        python3.12
        python3.11
    )

    for candidate in "${candidates[@]}"; do
        [[ -n "$candidate" ]] || continue
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
            command -v "$candidate"
            return
        fi
    done

    fail "Python 3.11 or newer is required. Set PYTHON_BIN to a compatible interpreter."
}

version_is_published() {
    "$python_bin" - "$version" "$PYPI_JSON_URL" <<'PY'
import json
import sys
import urllib.error
import urllib.request

version, url = sys.argv[1:]
try:
    with urllib.request.urlopen(url, timeout=15) as response:
        releases = json.load(response)["releases"]
except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError) as error:
    print(f"Could not check PyPI releases: {error}", file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(version not in releases)
PY
}

update_versions() {
    "$python_bin" - "$version" <<'PY'
from pathlib import Path
import re
import sys

version = sys.argv[1]
files = {
    Path("pyproject.toml"): (
        r'(?m)^version = "[^"]+"$',
        f'version = "{version}"',
    ),
    Path("src/yt_transcript/__init__.py"): (
        r'(?m)^__version__ = "[^"]+"$',
        f'__version__ = "{version}"',
    ),
}

for path, (pattern, replacement) in files.items():
    content = path.read_text()
    updated, count = re.subn(pattern, replacement, content, count=1)
    if count != 1:
        raise SystemExit(f"Could not find exactly one version declaration in {path}")
    path.write_text(updated)
PY
}

confirm_release() {
    [[ "$assume_yes" == true ]] && return

    printf '\nRelease %s to PyPI from %s? [y/N] ' "$version" "$(git rev-parse --short HEAD)"
    read -r answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || fail "Release cancelled"
}

version=""
assume_yes=false
skip_install=false

while (($#)); do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --yes)
            assume_yes=true
            ;;
        --skip-install)
            skip_install=true
            ;;
        --*)
            fail "Unknown option: $1"
            ;;
        *)
            [[ -z "$version" ]] || fail "Only one version may be supplied"
            version="$1"
            ;;
    esac
    shift
done

[[ -n "$version" ]] || { usage >&2; exit 1; }
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "VERSION must use X.Y.Z format"

require_command git

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

[[ "$(git rev-parse --show-toplevel)" == "$repo_root" ]] || fail "Script must run inside its repository"
[[ "$(git branch --show-current)" == "main" ]] || fail "Releases must be made from the main branch"
[[ -z "$(git status --porcelain)" ]] || fail "Working tree must be clean before releasing"

printf 'Checking origin/main...\n'
git fetch --quiet origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || fail "main must match origin/main before releasing"

python_bin="$(select_python)"
printf 'Using %s (%s)\n' "$python_bin" "$("$python_bin" --version 2>&1)"

if version_is_published; then
    fail "Version $version already exists on PyPI; choose a new version"
else
    published_status=$?
    [[ "$published_status" -eq 1 ]] || fail "Could not confirm whether version $version already exists on PyPI"
fi

confirm_release

release_temp="$(mktemp -d "${TMPDIR:-/tmp}/yt-transcript-release.XXXXXX")"
trap 'rm -rf "$release_temp"' EXIT
release_python="$release_temp/venv/bin/python"
release_pipx="$release_temp/venv/bin/pipx"
artifact_dir="$release_temp/artifacts"
mkdir -p "$artifact_dir"

printf '\nPreparing an isolated release environment...\n'
"$python_bin" -m venv "$release_temp/venv"
"$release_python" -m pip install --quiet --upgrade pip
"$release_python" -m pip install --quiet build twine pytest pipx

printf 'Running tests...\n'
"$release_python" -m pip install --quiet --editable .
"$release_python" -m pytest

printf 'Updating package version to %s...\n' "$version"
update_versions

printf 'Building and checking release artifacts...\n'
"$release_python" -m build --outdir "$artifact_dir"
"$release_python" -m twine check "$artifact_dir"/*

wheel_files=("$artifact_dir"/yt_transcript_cli-"$version"-*.whl)
sdist="$artifact_dir/yt_transcript_cli-$version.tar.gz"
[[ ${#wheel_files[@]} -eq 1 && -f "${wheel_files[0]}" ]] || fail "Expected exactly one wheel for version $version"
[[ -f "$sdist" ]] || fail "Expected source distribution not found: $sdist"

mkdir -p dist
cp "${wheel_files[0]}" "$sdist" dist/

if ! git diff --quiet -- pyproject.toml src/yt_transcript/__init__.py; then
    unexpected_changes="$(git status --porcelain --untracked-files=no \
        | grep -Ev '^ M (pyproject\.toml|src/yt_transcript/__init__\.py)$' || true)"
    [[ -z "$unexpected_changes" ]] || fail "Tracked files changed during the release; inspect git status before continuing"

    printf 'Committing and pushing the release version...\n'
    git status --short
    git add pyproject.toml src/yt_transcript/__init__.py
    git commit -m "Release version $version"
    [[ -z "$(git status --porcelain)" ]] || fail "Working tree changed during the release; inspect git status before pushing"
    git push origin main
fi

printf 'Uploading %s to PyPI...\n' "$version"
"$release_python" -m twine upload "${wheel_files[0]}" "$sdist"

if [[ "$skip_install" == false ]]; then
    printf 'Waiting for the release to become available...\n'
    for attempt in {1..12}; do
        if version_is_published; then
            break
        fi
        if [[ "$attempt" == 12 ]]; then
            fail "PyPI has not exposed version $version yet; reinstall it after propagation completes"
        fi
        sleep 5
    done

    printf 'Reinstalling %s with pipx...\n' "$PACKAGE_NAME"
    "$release_pipx" install --force --pip-args="--no-cache-dir" "$PACKAGE_NAME==$version"
    "$release_pipx" runpip "$PACKAGE_NAME" show "$PACKAGE_NAME"
fi

printf '\nRelease %s completed successfully.\n' "$version"
