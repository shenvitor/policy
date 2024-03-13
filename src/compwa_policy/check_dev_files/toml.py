"""Configuration for working with TOML files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit
from ruamel.yaml import YAML

from compwa_policy.errors import PrecommitError
from compwa_policy.utilities import COMPWA_POLICY_DIR, CONFIG_PATH, vscode
from compwa_policy.utilities.executor import Executor
from compwa_policy.utilities.match import filter_patterns
from compwa_policy.utilities.precommit.struct import Hook, Repo
from compwa_policy.utilities.pyproject import ModifiablePyproject
from compwa_policy.utilities.toml import to_toml_array

if TYPE_CHECKING:
    from compwa_policy.utilities.precommit import ModifiablePrecommit

__INCORRECT_TAPLO_CONFIG_PATHS = [
    Path("taplo.toml"),
]


def main(precommit: ModifiablePrecommit) -> None:
    trigger_files = [
        CONFIG_PATH.pyproject,
        CONFIG_PATH.taplo,
        *__INCORRECT_TAPLO_CONFIG_PATHS,
    ]
    if not any(f.exists() for f in trigger_files):
        return
    with Executor() as do:
        do(_rename_taplo_config)
        do(_update_taplo_config)
        do(_update_precommit_repo, precommit)
        do(_update_tomlsort_config)
        do(_update_tomlsort_hook, precommit)
        do(_update_vscode_extensions)


def _update_tomlsort_config() -> None:
    sort_first = [
        "build-system",
        "project",
        "tool.setuptools",
        "tool.setuptools_scm",
    ]
    expected_config = dict(
        all=False,
        ignore_case=True,
        in_place=True,
        sort_first=to_toml_array(sort_first),
        sort_table_keys=True,
        spaces_indent_inline_array=4,
        trailing_comma_inline_array=True,
    )
    with ModifiablePyproject.load() as pyproject:
        tool_table = pyproject.get_table("tool", create=True)
        if tool_table.get("tomlsort") == expected_config:
            return
        tool_table["tomlsort"] = expected_config
        pyproject.append_to_changelog("Updated toml-sort configuration")


def _update_tomlsort_hook(precommit: ModifiablePrecommit) -> None:
    expected_hook = Repo(
        repo="https://github.com/pappasam/toml-sort",
        rev="",
        hooks=[Hook(id="toml-sort", args=YAML(typ="rt").load("[--in-place]"))],
    )
    excludes = filter_patterns([
        "**/Manifest.toml",
        "**/Project.toml",
        "labels*.toml",
        "labels/*.toml",
    ])
    if excludes:
        regex_excludes = sorted(_to_regex(r) for r in excludes)
        expected_hook["hooks"][0]["exclude"] = (
            "(?x)^(" + "|".join(regex_excludes) + ")$"
        )
    precommit.update_single_hook_repo(expected_hook)


def _rename_taplo_config() -> None:
    for path in __INCORRECT_TAPLO_CONFIG_PATHS:
        if not path.exists():
            continue
        shutil.move(path, CONFIG_PATH.taplo)
        msg = f"Renamed {path} to {CONFIG_PATH.taplo}"
        raise PrecommitError(msg)


def _update_taplo_config() -> None:
    template_path = COMPWA_POLICY_DIR / ".template" / CONFIG_PATH.taplo
    if not CONFIG_PATH.taplo.exists():
        shutil.copyfile(template_path, CONFIG_PATH.taplo)
        msg = f"Added {CONFIG_PATH.taplo} config for TOML formatting"
        raise PrecommitError(msg)
    with open(template_path) as f:
        expected = tomlkit.load(f)

    excludes = filter_patterns(expected["exclude"])  # type:ignore[arg-type]
    if excludes:
        sorted_excludes = sorted(excludes, key=str.lower)
        expected["exclude"] = to_toml_array(sorted_excludes, enforce_multiline=True)
    else:
        del expected["exclude"]
    with open(CONFIG_PATH.taplo) as f:
        existing = tomlkit.load(f)
    expected_str = tomlkit.dumps(expected, sort_keys=True)
    existing_str = tomlkit.dumps(existing)
    if existing_str.strip() != expected_str.strip():
        with open(CONFIG_PATH.taplo, "w") as stream:
            stream.write(expected_str)
        msg = f"Updated {CONFIG_PATH.taplo} config file"
        raise PrecommitError(msg)


def _update_precommit_repo(precommit: ModifiablePrecommit) -> None:
    expected_hook = Repo(
        repo="https://github.com/ComPWA/mirrors-taplo",
        rev="",
        hooks=[Hook(id="taplo")],
    )
    precommit.update_single_hook_repo(expected_hook)


def _update_vscode_extensions() -> None:
    # cspell:ignore bungcip tamasfe
    with Executor() as do:
        do(vscode.add_extension_recommendation, "tamasfe.even-better-toml")
        do(vscode.remove_extension_recommendation, "bungcip.better-toml", unwanted=True)


def _to_regex(glob: str) -> str:
    r"""Convert glob pattern to regex.

    >>> _to_regex("**/*.toml")
    '.*/.*\\.toml'
    """
    return glob.replace("**", "*").replace(".", r"\.").replace("*", r".*")
