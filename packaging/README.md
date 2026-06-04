# Packaging — Homebrew + winget release steps

The `release.yml` GitHub Actions workflow publishes the wheel to PyPI and the
PyInstaller binaries to the GitHub release. The `homebrew_winget` job in that
workflow is intentionally an `echo` stub: pushing the Homebrew formula and the
winget manifest is a manual follow-up because both downstream repos require
human review.

This document is the runbook for that follow-up.

## When to run

After a `v*` tag has been pushed and:

- the `pypi` job is green (wheel is live on <https://pypi.org/project/pgntui/>),
- the `binaries` job is green (all four artifacts attached to the GitHub
  release).

## Inputs

For each release you need the SHA-256 of:

| Channel  | Artifact                                                                 |
|----------|--------------------------------------------------------------------------|
| Homebrew | sdist from PyPI: `pgntui-<version>.tar.gz`                              |
| winget   | Windows binary from GitHub release: `pgntui-windows-x86_64.exe`         |

### Compute sha256

macOS / Linux:

    shasum -a 256 pgntui-0.2.2.tar.gz
    shasum -a 256 pgntui-windows-x86_64.exe

Windows (PowerShell):

    Get-FileHash -Algorithm SHA256 pgntui-0.2.2.tar.gz
    Get-FileHash -Algorithm SHA256 pgntui-windows-x86_64.exe

## Step 1 — Update the stubs in this repo

Edit on a release branch (or directly on `main` after the tag):

- `packaging/homebrew/pgntui.rb`
  - Bump the version in the `url` line (PyPI sdist URL).
  - Replace `REPLACE_ON_RELEASE` with the sdist SHA-256.

- `packaging/winget/phobic.pgntui.yaml`
  - Bump `PackageVersion`.
  - Bump the `InstallerUrl` (`v<version>` in the path).
  - Replace `REPLACE_ON_RELEASE` with the Windows binary SHA-256.

Commit:

    git commit -am "chore(packaging): refresh homebrew + winget stubs for v<version>"

## Step 2 — Open the Homebrew PR

The formula lives in <https://github.com/phobicdotno/homebrew-tap>.

1. Clone the tap repo (or `gh repo clone phobicdotno/homebrew-tap`).
2. Replace `Formula/pgntui.rb` with the updated file from this repo.
3. Locally sanity-check:

       brew install --build-from-source ./Formula/pgntui.rb
       pgntui --help

4. Open a PR; the tap is single-maintainer so self-merge is fine once the
   build succeeds.

## Step 3 — Open the winget PR

1. Fork <https://github.com/microsoft/winget-pkgs> if you haven't already.
2. Drop the updated YAML at
   `manifests/p/phobic/pgntui/<version>/phobic.pgntui.yaml` (mirror the
   directory structure of an existing entry).
3. Validate locally:

       winget validate --manifest manifests/p/phobic/pgntui/<version>

4. Open a PR to `microsoft/winget-pkgs`. Their bots run smoke tests and an
   automated installer check; expect a 1-3 day turnaround.

## Step 4 — Verify on clean machines

Don't announce the release until both channels install cleanly on a fresh
host:

    # macOS
    brew install phobicdotno/tap/pgntui
    pgntui --help

    # Windows
    winget install --id phobic.pgntui
    pgntui --help

If install fails, revert the version line in the failing manifest and ship a
patch release rather than leaving a broken entry in the channel.

## Automation backlog

The `homebrew_winget` job in `.github/workflows/release.yml` could:

- compute the sha256s itself once the binaries are uploaded,
- patch this repo's stubs,
- open the Homebrew tap PR via `gh pr create`,
- open the winget PR via `wingetcreate`.

That's tracked but not implemented — for now the job is the stub `echo` that
reminds whoever is releasing to follow this runbook.
