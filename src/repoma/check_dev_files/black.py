"""Check :file:`pyproject.toml` black config."""
from textwrap import dedent
from typing import List, Optional

from ruamel.yaml.comments import CommentedMap

from repoma.errors import PrecommitError
from repoma.utilities import CONFIG_PATH, natural_sorting
from repoma.utilities.executor import Executor
from repoma.utilities.precommit import (
    find_repo,
    load_round_trip_precommit_config,
    update_precommit_hook,
    update_single_hook_precommit_repo,
)
from repoma.utilities.pyproject import load_pyproject
from repoma.utilities.setup_cfg import get_supported_python_versions


def main() -> None:
    if not CONFIG_PATH.pyproject.exists():
        return
    config = _load_black_config()
    executor = Executor()
    executor(_check_line_length, config)
    executor(_check_activate_preview, config)
    executor(_check_option_ordering, config)
    executor(_check_target_versions, config)
    executor(_check_pyproject)
    executor(_update_precommit_repo)
    executor(_update_precommit_nbqa_hook)
    executor.finalize()


def _load_black_config(content: Optional[str] = None) -> dict:
    config = load_pyproject(content)
    return config.get("tool", {}).get("black", {})


def _check_activate_preview(config: dict) -> None:
    expected_option = "preview"
    if config.get(expected_option) is not True:
        raise PrecommitError(dedent(f"""
            An option in pyproject.toml is wrong or missing. Should be:

            [tool.black]
            {expected_option} = true
            """).strip())


def _check_line_length(config: dict) -> None:
    if config.get("line-length") is not None:
        raise PrecommitError(
            "pyproject.toml should not specify a line-length (default to 88)."
        )


def _check_option_ordering(config: dict) -> None:
    options = list(config)
    sorted_options = sorted(config, key=natural_sorting)
    if sorted_options != options:
        error_message = dedent("""
            Options in pyproject.toml should be alphabetically sorted:

            [tool.black]
            """).strip()
        for option in sorted_options:
            error_message += f"\n{option} = ..."
        raise PrecommitError(error_message)


def _check_target_versions(config: dict) -> None:
    target_versions = config.get("target-version", [])
    supported_python_versions = get_supported_python_versions()
    expected_target_versions = sorted(
        "py" + s.replace(".", "") for s in supported_python_versions
    )
    if target_versions != expected_target_versions:
        error_message = dedent("""
            Black target versions in pyproject.toml should be as follows:

            [tool.black]
            target-version = [
            """).strip()
        for version in expected_target_versions:
            error_message += f"\n    '{version}',"
        error_message += "\n]"
        raise PrecommitError(error_message)


def _update_precommit_repo() -> None:
    expected_hook = CommentedMap(
        repo="https://github.com/psf/black",
        hooks=[CommentedMap(id="black")],
    )
    update_single_hook_precommit_repo(expected_hook)


def _update_precommit_nbqa_hook() -> None:
    update_precommit_hook(
        repo_url="https://github.com/nbQA-dev/nbQA",
        expected_hook=CommentedMap(
            id="nbqa-black",
            additional_dependencies=["black>=22.1.0"],
        ),
    )


def _check_pyproject() -> None:
    if not CONFIG_PATH.precommit.exists():
        return
    config, _ = load_round_trip_precommit_config()
    nbqa_repo = find_repo(config, "https://github.com/nbQA-dev/nbQA")
    if nbqa_repo is None:
        return
    nbqa_config = _load_nbqa_black_config()
    if nbqa_config != ["--line-length=85"]:
        error_message = dedent("""
            Configuration of nbqa-black in pyproject.toml should be as follows:

            [tool.nbqa.addopts]
            black = [
                "--line-length=85",
            ]

            This is to ensure that code blocks render nicely in the sphinx-book-theme.
            """).strip()
        raise PrecommitError(error_message)


def _load_nbqa_black_config(content: Optional[str] = None) -> List[str]:
    # cspell:ignore addopts
    config = load_pyproject(content)
    return config.get("tool", {}).get("nbqa", {}).get("addopts", {}).get("black", {})
