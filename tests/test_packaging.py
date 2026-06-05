from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_has_full_classifiers() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    for cls in (
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Terminals",
    ):
        assert cls in text


def test_release_workflow_exists_and_targets_pypi() -> None:
    wf = (ROOT / ".github/workflows/release.yml").read_text()
    assert "pypa/gh-action-pypi-publish" in wf
    assert "phobicdotno/pgntui" in wf or "${{ github.repository }}" in wf


def test_pyinstaller_spec_exists() -> None:
    assert (ROOT / "pgntui.spec").exists()


def test_homebrew_tap_stub_exists() -> None:
    tap = (ROOT / "packaging/homebrew/pgntui.rb").read_text()
    assert "class Pgntui" in tap
    assert "phobicdotno/homebrew-tap" in tap


def test_winget_manifest_stub_exists() -> None:
    manifest = (ROOT / "packaging/winget/phobic.pgntui.yaml").read_text()
    assert "PackageIdentifier: phobic.pgntui" in manifest


def test_force_include_covers_all_package_data_files() -> None:
    """Regression: every non-.py data file under decode/, themes/builtin/ and
    examples/ must have a wheel force-include entry, and every entry must
    point at a file that exists. v0.3.4's first release run failed because
    examples/containers/main.json was renamed without updating the map."""
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mapping = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    included = set(mapping)
    on_disk = set()
    for sub in ("decode", "themes/builtin", "examples"):
        for path in (ROOT / "src/pgntui" / sub).rglob("*"):
            if path.is_dir() or path.suffix in (".py", ".pyc") or "__pycache__" in path.parts:
                continue
            on_disk.add(path.relative_to(ROOT).as_posix())
    assert on_disk - included == set(), (
        f"missing force-include entries: {sorted(on_disk - included)}"
    )
    assert included - on_disk == set(), f"stale force-include entries: {sorted(included - on_disk)}"
