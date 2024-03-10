"""Check existence of pre-commit hook for EditorConfig.

If a repository has an ``.editorconfig`` file, it should have an `EditorConfig
pre-commit hook
<https://github.com/editorconfig-checker/editorconfig-checker.python>`_.
"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from ruamel.yaml.scalarstring import FoldedScalarString

from compwa_policy.utilities import CONFIG_PATH
from compwa_policy.utilities.precommit.struct import Hook, Repo

if TYPE_CHECKING:
    from compwa_policy.utilities.precommit import ModifiablePrecommit


def main(precommit: ModifiablePrecommit, no_python: bool) -> None:
    if CONFIG_PATH.editorconfig.exists():
        _update_precommit_config(precommit, no_python)


def _update_precommit_config(precommit: ModifiablePrecommit, no_python: bool) -> None:
    hook = Hook(
        id="editorconfig-checker",
        name="editorconfig",
        alias="ec",
    )
    if not no_python:
        msg = R"""
        (?x)^(
          .*\.py
        )$
        """
        excludes = dedent(msg).strip()
        hook["exclude"] = FoldedScalarString(excludes)

    expected_hook = Repo(
        repo="https://github.com/editorconfig-checker/editorconfig-checker.python",
        rev="",
        hooks=[hook],
    )
    precommit.update_single_hook_repo(expected_hook)
