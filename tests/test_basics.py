"""Version/release-note consistency and the no-UI entry point."""

from pgntui import __version__, about


def test_version_matches_release_notes() -> None:
    # The newest RELEASE_NOTES entry must name the current version, so the
    # About screen and header can never silently lag a release. Asserting
    # consistency (not a hardcoded literal) means a version bump can't break
    # this test as long as the changelog is updated alongside it.
    assert about.RELEASE_NOTES[0][0] == __version__


def test_main_returns_zero() -> None:
    from pgntui.__main__ import main

    assert main(["--check"]) == 0
