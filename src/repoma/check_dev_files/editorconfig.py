"""Check existence of pre-commit hook for EditorConfig.

If a repository has an ``.editorconfig`` file, it should have an `EditorConfig
pre-commit hook
<https://github.com/editorconfig-checker/editorconfig-checker.python>`_.
"""

from functools import lru_cache
from textwrap import dedent

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, FoldedScalarString

from repoma.errors import PrecommitError
from repoma.utilities import CONFIG_PATH
from repoma.utilities.precommit import find_repo, load_round_trip_precommit_config

__EDITORCONFIG_HOOK_ID = "editorconfig-checker"
__EDITORCONFIG_URL = (
    "https://github.com/editorconfig-checker/editorconfig-checker.python"
)


def main() -> None:
    if CONFIG_PATH.editorconfig.exists():
        _update_precommit_config()


def _update_precommit_config() -> None:
    if not CONFIG_PATH.precommit.exists():
        return
    expected_hook = __get_expected_hook_definition()
    existing_config, yaml = load_round_trip_precommit_config()
    repos: CommentedSeq = existing_config.get("repos", [])
    idx_and_repo = find_repo(existing_config, __EDITORCONFIG_URL)
    if idx_and_repo is None:
        idx = __determine_expected_index(existing_config)
        repos.insert(idx, expected_hook)
        repos.yaml_set_comment_before_after_key(
            idx if idx + 1 == len(repos) else idx + 1,
            before="\n",
        )
        yaml.dump(existing_config, CONFIG_PATH.precommit)
        raise PrecommitError(f"Added editorconfig hook to {CONFIG_PATH.precommit}")
    idx, existing_hook = idx_and_repo
    if not __is_equivalent(existing_hook, expected_hook):
        existing_rev = existing_hook.get("rev")
        if existing_rev is not None:
            expected_hook["rev"] = existing_rev
        repos[idx] = expected_hook
        repos.yaml_set_comment_before_after_key(idx + 1, before="\n")
        yaml.dump(existing_config, CONFIG_PATH.precommit)
        raise PrecommitError(f"Updated editorconfig hook in {CONFIG_PATH.precommit}")


@lru_cache(maxsize=None)
def __get_expected_hook_definition() -> CommentedMap:
    excludes = R"""
    (?x)^(
      .*\.py
    )$
    """
    excludes = dedent(excludes).strip()
    hook = {
        "id": __EDITORCONFIG_HOOK_ID,
        "name": "editorconfig",
        "alias": "ec",
        "exclude": FoldedScalarString(excludes),
    }
    dct = {
        "repo": __EDITORCONFIG_URL,
        "rev": DoubleQuotedScalarString(""),
        "hooks": [CommentedMap(hook)],
    }
    return CommentedMap(dct)


def __determine_expected_index(config: CommentedMap) -> int:
    repos: CommentedSeq = config["repos"]
    for i, repo_def in enumerate(repos):
        hook_id: str = repo_def["hooks"][0]["id"]
        if __EDITORCONFIG_HOOK_ID.lower() <= hook_id.lower():
            return i
    return len(repos)


def __is_equivalent(expected: CommentedMap, existing: CommentedMap) -> bool:
    def remove_rev(config: CommentedMap) -> dict:
        config_copy = dict(config)
        config_copy.pop("rev", None)
        return config_copy

    return remove_rev(expected) == remove_rev(existing)
