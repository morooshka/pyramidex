"""Regression tests for path-resolution bugs surfaced during 2026-04-26 re-init.

Bug A: bootstrap.TEMPLATE_PATH pointed at a deleted location after assets moved
       into the package. A simple existence check would have caught it.
Bug B: cli.DUMP was computed via Path(__file__).parent.parent.parent / "dump.yaml",
       which broke under `uv tool install .` because __file__ then lives in the
       uv-managed venv. The fix anchors DUMP to Path.cwd() instead.
"""

from pathlib import Path

from pyramidex import bootstrap, cli


def test_bootstrap_template_path_resolves_to_existing_file() -> None:
    assert bootstrap.TEMPLATE_PATH.exists(), (
        f"bootstrap.TEMPLATE_PATH does not exist: {bootstrap.TEMPLATE_PATH}. "
        "If assets moved, update TEMPLATE_PATH to the new location."
    )


def test_cli_template_path_resolves_to_existing_file() -> None:
    assert cli.TEMPLATE.exists(), (
        f"cli.TEMPLATE does not exist: {cli.TEMPLATE}. "
        "If assets moved, update TEMPLATE to the new location."
    )


def test_cli_dump_anchored_to_cwd_not_file() -> None:
    # DUMP must be CWD-relative so `pyramidex init` reads dump.yaml from the
    # directory the user invokes it in. Anchoring to __file__ silently breaks
    # under `uv tool install`, where __file__ lives inside a uv-managed venv.
    assert cli.DUMP == Path.cwd() / "dump.yaml", (
        f"cli.DUMP must be Path.cwd() / 'dump.yaml', got {cli.DUMP}. "
        "Do not anchor DUMP to __file__ - it breaks under `uv tool install`."
    )
