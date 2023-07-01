# pylint: disable=no-name-in-module
"""Helper functions for modifying :file:`.pre-commit.config.yaml`."""

import os.path
import re
from pathlib import Path
from textwrap import dedent
from typing import Any, List, Optional, Tuple, Type, TypeVar, Union

import attrs
import yaml
from attrs import define
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, PlainScalarString

from repoma.errors import PrecommitError

from . import CONFIG_PATH
from .yaml import create_prettier_round_trip_yaml


def load_round_trip_precommit_config(
    path: Path = CONFIG_PATH.precommit,
) -> Tuple[CommentedMap, YAML]:
    yaml_parser = create_prettier_round_trip_yaml()
    config = yaml_parser.load(path)
    return config, yaml_parser


def find_repo(
    config: CommentedMap, search_pattern: str
) -> Optional[Tuple[int, CommentedMap]]:
    """Find pre-commit hook definition and its index in pre-commit config."""
    repos: CommentedSeq = config.get("repos", [])
    for i, repo in enumerate(repos):
        url: str = repo.get("repo", "")
        if re.search(search_pattern, url):
            return i, repo
    return None


def update_single_hook_precommit_repo(expected_repo_def: CommentedMap) -> None:
    """Update the repo definition in :code:`.pre-commit-config.yaml`.

    If the repository is not yet listed under the :code:`repos` key, a new entry will
    be automatically inserted. If the repository exists, but the definition is not the
    same as expected, the entry in the YAML config will be updated.
    """
    if not CONFIG_PATH.precommit.exists():
        return
    config, yaml_parser = load_round_trip_precommit_config()
    repos: CommentedSeq = config.get("repos", [])
    repo_url: str = expected_repo_def["repo"]
    idx_and_repo = find_repo(config, repo_url)
    hook_id: str = expected_repo_def["hooks"][0]["id"]
    if idx_and_repo is None:
        if "rev" not in expected_repo_def:
            expected_repo_def.insert(1, "rev", DoubleQuotedScalarString(""))
        idx = _determine_expected_repo_index(config, hook_id)
        repos.insert(idx, expected_repo_def)
        repos.yaml_set_comment_before_after_key(
            idx if idx + 1 == len(repos) else idx + 1,
            before="\n",
        )
        yaml_parser.dump(config, CONFIG_PATH.precommit)
        msg = dedent(f"""
        Added {hook_id} hook to {CONFIG_PATH.precommit}. Please run

            pre-commit autoupdate --repo {repo_url}

        to update to the latest release of this pre-commit repository.
        """).strip()
        raise PrecommitError(msg)
    idx, existing_hook = idx_and_repo
    if not _is_equivalent_repo(existing_hook, expected_repo_def):
        existing_rev = existing_hook.get("rev")
        if existing_rev is not None:
            expected_repo_def.insert(1, "rev", PlainScalarString(existing_rev))
        repos[idx] = expected_repo_def
        repos.yaml_set_comment_before_after_key(idx + 1, before="\n")
        yaml_parser.dump(config, CONFIG_PATH.precommit)
        msg = f"Updated {hook_id} hook in {CONFIG_PATH.precommit}"
        raise PrecommitError(msg)


def _determine_expected_repo_index(config: CommentedMap, hook_id: str) -> int:
    repos: CommentedSeq = config["repos"]
    for i, repo_def in enumerate(repos):
        hooks: CommentedSeq = repo_def["hooks"]
        if len(hooks) != 1:
            continue
        if hook_id.lower() <= repo_def["hooks"][0]["id"].lower():
            return i
    return len(repos)


def _is_equivalent_repo(expected: CommentedMap, existing: CommentedMap) -> bool:
    def remove_rev(config: CommentedMap) -> dict:
        config_copy = dict(config)
        config_copy.pop("rev", None)
        return config_copy

    return remove_rev(expected) == remove_rev(existing)


def update_precommit_hook(repo_url: str, expected_hook: CommentedMap) -> None:
    """Update the pre-commit hook definition of a specific pre-commit repo.

    Just like :func:`update_precommit_repo`, this function updates the
    :code:`.pre-commit-config.yaml` file, but does this only for a specific hook
    definition *within* a pre-commit repository definition.
    """
    if not CONFIG_PATH.precommit.exists():
        return
    config, yaml_parser = load_round_trip_precommit_config()
    idx_and_repo = find_repo(config, repo_url)
    if idx_and_repo is None:
        return
    repo_idx, repo = idx_and_repo
    repo_name = repo_url.split("/")[-1]
    hooks: CommentedSeq = repo["hooks"]
    hook_idx = __find_hook_idx(hooks, expected_hook["id"])
    if hook_idx is None:
        hook_idx = __determine_expected_hook_idx(hooks, expected_hook["id"])
        hooks.insert(hook_idx, expected_hook)
        if hook_idx == len(hooks) - 1:
            repos: CommentedMap = config["repos"]
            repos.yaml_set_comment_before_after_key(repo_idx + 1, before="\n")
        yaml_parser.dump(config, CONFIG_PATH.precommit)
        msg = f"Added {expected_hook['id']!r} to {repo_name} pre-commit config"
        raise PrecommitError(msg)

    if hooks[hook_idx] != expected_hook:
        hooks[hook_idx] = expected_hook
        yaml_parser.dump(config, CONFIG_PATH.precommit)
        msg = f"Updated args of {expected_hook['id']!r} {repo_name} pre-commit hook"
        raise PrecommitError(msg)


def __find_hook_idx(hooks: CommentedSeq, hook_id: str) -> Optional[int]:
    msg = ""
    for i, hook in enumerate(hooks):
        msg += " " + hook["id"]
        if hook["id"] == hook_id:
            return i
    return None


def __determine_expected_hook_idx(hooks: CommentedSeq, hook_id: str) -> int:
    for i, hook in enumerate(hooks):
        if hook["id"] > hook_id:
            return i
    return len(hooks)


@define
class PrecommitCi:
    """https://pre-commit.ci/#configuration."""

    autofix_commit_msg: str = "[pre-commit.ci] auto fixes [...]"
    autofix_prs: bool = True
    autoupdate_commit_msg: str = "[pre-commit.ci] pre-commit autoupdate"
    autoupdate_schedule: str = "weekly"
    skip: Optional[List[str]] = None
    submodules: bool = False


@define
class Hook:
    """https://pre-commit.com/#pre-commit-configyaml---hooks."""

    id: str  # noqa: A003
    name: Optional[str] = None
    description: Optional[str] = None
    entry: Optional[str] = None
    alias: Optional[str] = None
    additional_dependencies: List[str] = []
    args: List[str] = []
    files: Optional[str] = None
    exclude: Optional[str] = None
    types: Optional[List[str]] = None
    require_serial: bool = False
    language: Optional[str] = None
    always_run: Optional[bool] = None
    pass_filenames: Optional[bool] = None


@define
class Repo:
    """https://pre-commit.com/#pre-commit-configyaml---repos."""

    repo: str
    hooks: List[Hook]
    rev: Optional[str] = None

    def get_hook_index(self, hook_id: str) -> Optional[int]:
        for i, hook in enumerate(self.hooks):
            if hook.id == hook_id:
                return i
        return None


@define
class PrecommitConfig:
    """https://pre-commit.com/#pre-commit-configyaml---top-level."""

    repos: List[Repo]
    ci: Optional[PrecommitCi] = None
    files: str = ""
    exclude: str = "^$"
    fail_fast: bool = False

    @classmethod
    def load(cls, path: Union[Path, str] = CONFIG_PATH.precommit) -> "PrecommitConfig":
        if not os.path.exists(path):
            raise PrecommitError(f"This repository contains no {path}")
        with open(path) as stream:
            definition = yaml.safe_load(stream)
        return fromdict(definition, PrecommitConfig)

    def find_repo(self, search_pattern: str) -> Optional[Repo]:
        for repo in self.repos:
            url = repo.repo
            if re.search(search_pattern, url):
                return repo
        return None

    def get_repo_index(self, search_pattern: str) -> Optional[int]:
        for i, repo in enumerate(self.repos):
            url = repo.repo
            if re.search(search_pattern, url):
                return i
        return None


_T = TypeVar("_T", Hook, PrecommitCi, PrecommitConfig, Repo)


def asdict(inst: Any) -> dict:
    return attrs.asdict(
        inst,
        recurse=True,
        filter=lambda a, v: a.init and a.default != v,
    )


def fromdict(definition: dict, typ: Type[_T]) -> _T:
    if typ in {Hook, PrecommitCi}:
        return typ(**definition)  # type: ignore[return-value]
    if typ is Repo:
        definition = {
            **definition,
            "hooks": [fromdict(i, Hook) for i in definition["hooks"]],
        }
        return Repo(**definition)  # type: ignore[return-value]
    if typ is PrecommitConfig:
        definition = {
            **definition,
            "repos": [fromdict(i, Repo) for i in definition["repos"]],
        }
        if "ci" in definition:
            definition["ci"] = fromdict(definition["ci"], PrecommitCi)
        return PrecommitConfig(**definition)  # type: ignore[return-value]
    raise NotImplementedError(f"No implementation for type {typ.__name__}")
