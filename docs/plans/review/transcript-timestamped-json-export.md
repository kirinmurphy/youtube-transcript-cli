---
id: 3qznl8b1
priority: none
next_action: Await explicit human approval of reviewed commit aebb70c5e9eb9468a22ed41583117a180258d05d.
blocked_by: []
depends_on: []
related: []
reviewed_commit: 5b5a3ba9d32bfe1f02ff59e7cb7fcd9d8bb02cf5
worktree: transcript-timestamped-json-export
---

# Timestamped exports for research workflows

## Summary

Give research tools timestamped transcript files and a reliable way to locate them on repeated runs. Add `--format json` and print existing file paths when downloads are skipped. Keep this package standalone so Knowledge Researcher can consume it as a dependency.

## Goals

- Preserve each fetched segment's text, start time, duration, and order in JSON exports.
- Report usable file paths for newly saved and cached transcripts, including with `--quiet`.
- Preserve default text exports and the existing Python library API.

## Current state

Preparation baseline, before this implementation:

| Area | Repository evidence |
| --- | --- |
| Segment data | `src/yt_transcript/core.py`: `fetch_transcript()` returns `to_raw_data()`; its documented fields are `text`, `start`, and `duration`. |
| Text export | `to_text()` joins segment text; `src/yt_transcript/cli.py` always saves `transcript_{VIDEO_ID}.txt`. |
| Cache hit | `process_video()` checks whether the output path exists, logs it to stderr, and returns `'skipped'` without printing the path to stdout. |
| New download | `process_video()` prints its saved path to stdout and returns `'success'`. |
| Input modes | `main()` passes batch URLs or file input to `process_urls()`; `run_repl()` also calls `process_urls()`. |
| Verification tooling | The inspected repository files include no test directory, test runner configuration, or CI workflow. `pyproject.toml` declares Python 3.11+ and the runtime dependencies. |

### Repository and related-plan review

The reviewed checkout is `main` at `5b5a3ba9d32bfe1f02ff59e7cb7fcd9d8bb02cf5`; that commit is the current implementation baseline. All lifecycle folders were inspected: this is the only plan document, with no dependency links or overlapping stories to reconcile. There is no related implementation commit or active-story lifecycle drift.

`README.md` owns usage and library documentation; `PUBLISHING.md` covers releases. No separate documentation inventory or repository test, lint, type-check, or health-check command is present in the inspected files.

## Proposed design

### File format and cache contract

Add an argparse option `--format` with choices `text` and `json`, defaulting to `text`. The option chooses the file representation; stdout continues to report paths.

| Selection | File | Contents |
| --- | --- | --- |
| Omitted or `--format text` | `transcript_{VIDEO_ID}.txt` | Existing continuous text output |
| `--format json` | `transcript_{VIDEO_ID}.json` | JSON array of the original segment dictionaries |

Write JSON as UTF-8 using Python's standard `json` module. Preserve numeric timing values, Unicode text, segment order, and any additional segment fields returned by the fetcher. Add no metadata wrapper or new runtime dependency.

Illustrative JSON file contents, not captured output:

```json
[
  {"text": "First sentence.", "start": 1.25, "duration": 2.5},
  {"text": "Next sentence.", "start": 4.0, "duration": 1.75}
]
```

Each format has its own cache file. A `.txt` file does not satisfy a JSON request, since it lacks timestamps; fetch the segments and save `.json` when needed. With the existing default `skip_existing=True`, a matching file is reused without fetching or rewriting it. Preserve `skip_existing=False` for callers that explicitly request a rewrite. Preserve the existing check for empty or whitespace-only transcript text before saving either format.

### Paths for automation

For each successful save or matching cache hit, print `str(output_path)` once on stdout. Keep the current relative-or-absolute path convention determined by `--output-dir`; do not change `process_video()`'s status return values or aggregate counters.

Batch automation uses `--quiet`, which already suppresses the batch separator blank lines. With it, stdout must contain one nonempty path line per successful or cached video occurrence, in processing order. Keep progress, skip notices, errors, and batch summaries on stderr. Failed videos emit no path. Preserve current duplicate-input handling and exit statuses, including success when every video is cached.

Proposed invocation after implementation:

```sh
yt-transcript-cli --format json --quiet --output-dir transcripts "https://www.youtube.com/watch?v=dQw4w9WgXc"
```

On a successful first run and on a matching cached rerun, stdout identifies `transcripts/transcript_dQw4w9WgXc.json`. The JSON is read from that file. Interactive prompts and summaries remain human-facing; `--quiet` batch mode is the automation contract.

### Ownership and mode propagation

Keep file selection and serialization in `src/yt_transcript/cli.py`, alongside the existing file writer. Pass the selected format from `main()` through `process_urls()` and `run_repl()` to `process_video()`. Append a defaulted format parameter after each function's existing parameters so current calls retain text behavior. Update affected CLI descriptions and docstrings to describe both formats.

`core.py` already supplies the required segments. Preserve `fetch_transcript()`, `to_text()`, and the exports in `src/yt_transcript/__init__.py`.

## Implementation checklist

- [x] Create `tests/test_cli.py` with temporary output directories, captured streams, and stubbed transcript/playlist fetches. Run focused cases first to establish failures for missing JSON parsing and missing cached-path output.
- [x] Add `--format {text,json}` in `main()` and append a defaulted format parameter to `process_urls()`, `run_repl()`, and `process_video()`. Preserve existing positional arguments, including `skip_existing`.
- [x] Select the filename suffix and serialize segments inside `process_video()`. Keep the shared empty-text check and text output unchanged.
- [x] Print cached paths before returning `'skipped'`. Verify counters, duplicate occurrences, forced rewrites, and delay handling remain compatible.
- [x] Complete the acceptance checks below through real parsing, batch processing, and queued interactive input, using temporary files and stubbed network responses.
- [x] Update README usage, options, output behavior, cache limitations, and library guidance; reconcile the CLI's module description and help with both formats.
- [x] Run the complete CLI regression module in the project environment and check CLI help against README examples.

## Validation

Add `tests/test_cli.py` using standard-library `unittest`, temporary directories, stream capture, and `unittest.mock`. Stub transcript and playlist network boundaries, while exercising real CLI parsing, file serialization, cache files, and stdout. No live YouTube requests are needed for these changes.

| Acceptance case | Required assertion |
| --- | --- |
| Default and explicit text | Both save the existing joined text to `.txt`. |
| JSON round trip | Parsed file equals the supplied segment list, including fractional times, duration, Unicode, and an extra field. |
| Same-format cache, text and JSON | Existing bytes stay unchanged, fetching is not called, and the path prints once. |
| Forced rewrite, text and JSON | Calling `process_video()` with `skip_existing=False` replaces matching cached bytes and emits one path. |
| Cross-format cache | Existing `.txt` does not suppress JSON fetching; existing `.json` does not suppress text fetching. |
| Quiet batch stdout | A mixed fresh/cached batch emits exactly its ordered path lines, without progress or summaries. |
| Non-quiet cache hit | The path prints once on stdout, and the skip notice remains on stderr. |
| All-cached batch | Paths print and `main()` succeeds without fetching transcripts. |
| Multiple videos, playlist, and URL file | The selected format reaches every resolved video and files use the correct suffix. |
| Duplicate inputs | Repeated resolved IDs produce repeated ordered path lines, one saved result and subsequent skipped results. |
| Delay compatibility | Stub `time.sleep`; fresh/failed non-final results retain the configured delay, while skipped and final results add no delay. |
| Interactive mode | Enter through `main()` with JSON selected, queue a URL, process it, and quit; verify the JSON file. Cover explicit `-i` and implicit interactive entry. |
| Existing Python calls | Existing positional CLI-helper calls still default to text; `fetch_transcript()`, `to_text()`, and package exports retain their contracts. |
| Invalid format | argparse rejects it with exit status 2 before fetching or creating an output directory. |
| Empty or whitespace-only transcript | Processing fails, creates no transcript file, and emits no path in either format. |
| Fetch failures and mixed outcomes | Failed videos emit no paths; all-failed exits 1 and partial success exits 2. |

Implementation environment setup (Python 3.11+ required; use an equivalent available interpreter if needed):

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
```

Implementation verification commands (proposed; the test file and project environment do not exist yet):

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m yt_transcript.cli --help
```

Check the updated CLI help and README examples against the implemented parser. Promotion inspection found `python3` at 3.9.6 and an available `python3.11` at 3.11.15; neither has the declared runtime dependencies installed. Environment setup belongs to implementation. Plan-only validation uses the selected plan's `roborepo plans validate <plan> --json` command and a documentation review; implementation tests are not evidence until executed during implementation.

## Documentation impact

`README.md` is the inspected user-facing usage and library reference. Add the format option with its text default, both filename extensions, a labeled JSON segment example, and a quiet batch example showing that fresh and cached results both print paths. Clarify that `fetch_transcript()` already provides timestamped segments to Python callers. Update the behavior section's text-only and skip descriptions accordingly.

## Scope and limitations

Knowledge Researcher integration happens in its own project. This work adds the dependency's export contract; it adds no downstream agent code, packaging changes, new cache metadata, or output formats beyond text and JSON.

The current cache identifies files by video ID alone. Adding a format suffix separates representations but does not distinguish requested languages. Existing files are trusted by existence rather than validated. Preserve those policies here and document that cache reuse does not verify language or file contents. JSON requires a new fetch when only text is cached, so that conversion still depends on upstream availability.

## Open questions

None for the requested scope. Default text compatibility, raw segment arrays, format-specific cache files, and stdout paths follow the requested behavior and existing CLI structure.


## Execution record

- Mode: start. Base branch: `main`. Feature branch: `codex/transcript-timestamped-json-export`.
- Git administrative worktree name: `transcript-timestamped-json-export`.
- Starting implementation commit: `06c43612c2727e9a10012fccb8442f2be2321b2e`.
- Start transition: `5e05e33cb43d8d426fc70b52d97bc3694b6675be`; validator APPROVED with zero correction passes and no stale links.
- All seven implementation checklist objectives are complete. No blocked tasks or scope changes.
- `src/yt_transcript/cli.py` owns suffix selection and JSON serialization, with appended defaulted format arguments throughout batch and interactive flows. `core.py`, package exports, and packaging configuration are unchanged.
- `README.md` documents format selection, file contents, automation paths, cache limitations, exit statuses, and the existing segment-based library API.

### Verification evidence

- Before implementation, focused JSON parsing and cached-text-path tests failed on the missing behaviors. Temporary-directory cleanup restrictions were isolated from the regression assertions before implementation.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`: 21 tests passed. The tests exercise the acceptance matrix using real parsing, real temporary files, queued interactive input, and stubbed transcript/playlist network boundaries.
- `PYTHONPATH=src .venv/bin/python -m yt_transcript.cli --help`: exits 0 and lists `--format {text,json}`, its text default, and quiet batch path behavior.
- `git diff --check`: passed.
- Direct demonstration used `main()` with `--format json --quiet --output-dir transcripts` and a stubbed transcript fetch. Fresh and cached runs both emitted exactly `transcripts/transcript_dQw4w9WgXcQ.json`, stderr was empty, the JSON file round-tripped to the supplied segments, and the fetch count was exactly one.
- No live YouTube requests were needed; upstream transcript availability is outside the changed export/cache behavior.
- No lint, type-check, health-check, or broader test command is configured in this repository's inspected files.

### Test environment

A Python 3.11.15 `.venv` was created in the implementation worktree. The host already caches `youtube-transcript-api` 1.2.4, `requests` 2.33.0, and their dependencies. The environment references these cached distributions through a local ignored `.pth` file, and the tests run the checkout with `PYTHONPATH=src`.

Normal `python3.11 -m venv .venv` bootstrapping and editable installation could not complete under this environment's file restrictions: certificate-file operations and removal of temporary directories returned `PermissionError`. Offline editable-install and direct-build attempts also failed on temporary-directory removal. These are environment setup limitations; no dependency, package configuration, or runtime code was changed to work around them.

The source-module CLI was started for help, the fresh/cache demonstration, and a subprocess cache check with a relative output path. This is a local CLI with no server or shareable URL.

## Decision Log

- User decision: create the isolated feature branch/worktree proposed for this run, preserving the primary checkout's branch and unrelated untracked setup files.
- Use existing cached dependencies in the ignored test environment rather than changing project dependencies or disabling transport verification. The cache supplies the declared runtime packages without certificate-file access; this enables the full source-level CLI verification while leaving the installed-command check explicit below.
- Use best-effort temporary-directory cleanup in regression fixtures. Strict cleanup raised platform `PermissionError` after the behavior assertions; ignoring cleanup errors preserves real file I/O and still attempts cleanup without disguising behavior failures.
- JSON uses UTF-8, literal Unicode, and two-space indentation. Compact JSON would preserve the same data; indentation makes research artifacts easier to inspect without changing the segment-array contract.

## Not tested

- [x] Install the package in a Python 3.11+ environment and verify that the installed `yt-transcript-cli --help` exposes `--format {text,json}`. Confirmed by the human on 2026-11-02: supplied terminal output shows Python 3.11.15, successful wheel build and installation of yt-transcript-cli 0.1.2 using `python -m pip install .`, and installed help showing the format choices and text default.

## Review

### Findings

None. Independent validation pass 1 found no `fix`, `escalate`, or `base` findings at `f7ff6aa`.

### Verification

- Validation: clean on pass 1 at `f7ff6aa` (fresh-context subagent). The initial validator launch was unavailable because of a usage limit; a subsequent launch completed the full read-only pass.
- The Validator inspected the full `git diff main...HEAD`, all acceptance criteria, code, tests, README, and verification gaps. It independently reran all 21 regression tests, CLI help, and `git diff --check`; all passed.
- The code review covered format propagation, serialization, cache separation, stdout ordering, backward compatibility, failures, delays, cohesion, state, and affected comments.
- Documentation review passed against technical-writing Core Writing Philosophy, `doc-shapes.md`, `section-guidance.md`, `representation.md`, `anti-patterns.md`, `review-loop.md`, supplied documentation requirements, and applicable paired skills. The existing README structure remains appropriate; documentation-set organization rules do not apply.
- Base failures: none reported by the Validator. Installed-command verification remains the one explicit Not tested entry.
- Canonical completion preflight passed all six checks before recording this review: assigned worktree, checked tasks outside Not tested, empty blockers, clean worktree, feature commit, and review-validator requirements. It passed again after the validation record was committed, and the submit command reran it successfully.
- Plan validation reports zero blocking findings and one advisory `UNCONFIRMED_NOT_TESTED` entry.
- No human approval has been requested or recorded. Implementation completion does not constitute human approval.


### Lifecycle handoff

- Submit transition: `f515f338e1415446ca8c96db052fc0aca0f7619c`; APPROVED with all six transition checks passing. The primary lifecycle copy is now in `docs/plans/review/transcript-timestamped-json-export.md`; this worktree's active-path copy remains authoritative for implementation details until base synchronization during review.
- Post-submit worktree validation: zero blocking findings; one advisory `UNCONFIRMED_NOT_TESTED`.
- Post-submit primary validation: zero blocking findings; advisories `UNCONFIRMED_NOT_TESTED` and `PLAN_EDITED_OUTSIDE_WORKTREE`. The submit commit is an exact plan-only rename (`R100`), with identical before/after blob `d50feeb52dcf3ebb3bdb6563f3a3f7e60806bc16`. Inspection of the installed plan tool's `checkOutsideEdits()` confirms that it checks the new review path at the merge base, where that path does not exist yet, and does not recognize the unchanged primary blob in this case. No primary plan body was edited and no merge was attempted. Base synchronization belongs to `/plan-review`.
- The feature worktree is clean after committing its records. Unrelated untracked plan-suite scaffolding in the primary checkout was preserved. Nothing was pushed, merged, or published.


### Human-review verification — 2026-11-02

- Base synchronization: `roborepo plans sync-base --json` reported `up-to-date` at `9465ac8a5e3b26849edc2d18482eecf34b9aa9a8`, with base `14c3120c1343f24c58c0b366177a86d56e7b2bed`. The existing merge brought main into the feature branch; the implementation has not landed on main.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`: all 21 tests passed again on the synchronized result.
- `PYTHONPATH=src .venv/bin/python -m yt_transcript.cli --help`: exited 0 and exposed `--format {text,json}` and the text default.
- `git diff --check`: passed. No broader test, lint, type, or health gate is configured in the inspected tracked files.
- Fresh-context Validator pass 1: clean, with no fix, escalate, or base findings. All 16 acceptance rows map to observable tests covering text compatibility, JSON fidelity, both cache formats, forced rewrites, cross-format fetching, ordered stdout, stderr separation, all-cached success, input modes, duplicates, delays, interactive modes, library calls, invalid formats, empty transcripts, and failures.
- README matches the implementation's format, cache, automation, and library contracts. CLI serialization and format propagation retain the existing ownership boundaries; core and package exports are unchanged.
- Installed-command verification remains blocked. An isolated source copy built with `from setuptools.build_meta import build_wheel; build_wheel("../wheel")` failed with `PermissionError` while removing its generated egg-info directory. A retry with elevated execution permission failed identically. No wheel installation or installed-command assertion ran. The earlier pip attempt also encountered restricted certificate-file access; no certificate restrictions were bypassed.
- Base failures: none established. The build check is environment-blocked, not classified as a code finding or a proven base failure.
- No implementation fixes were needed. One required Not tested entry remains unconfirmed; final approval was not requested.

### Manual verification resolution — 2026-11-02

- The human supplied terminal output confirming the remaining installation check: Python 3.11.15, successful wheel build and installation from the assigned feature worktree, and installed `yt-transcript-cli --help` displaying `--format {text,json}`. This resolves the earlier environment-blocked check; the earlier attempt records remain historical.
- Fresh Git reads confirmed clean primary and feature worktrees, unchanged base `14c3120c1343f24c58c0b366177a86d56e7b2bed`, and only plan-record changes since the tested and independently validated implementation at `9465ac8a5e3b26849edc2d18482eecf34b9aa9a8`. The 21 passing tests and clean Validator pass are reused for identical implementation content.
- All findings and required manual checks are resolved. Review is complete; human approval remains a separate pending decision.

### Result
- Status: complete
- Reviewed implementation commit: aebb70c5e9eb9468a22ed41583117a180258d05d
- Base commit: 14c3120c1343f24c58c0b366177a86d56e7b2bed

### Approval
- Decision: requested
