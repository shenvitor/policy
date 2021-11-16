# pylint: disable=no-name-in-module
"""Collection of helper functions that are used by all sub-hooks."""

import io
import json
import os
import re
from configparser import ConfigParser
from pathlib import Path
from typing import Callable, Iterable, List, NamedTuple, Optional, Tuple, Union

import yaml
from pydantic import BaseModel
from ruamel.yaml import YAML

import repoma
from repoma.errors import PrecommitError


class _ConfigFilePaths(NamedTuple):
    cspell: Path = Path(".cspell.json")
    editor_config: Path = Path(".editorconfig")
    flake8: Path = Path(".flake8")
    github_workflow_dir: Path = Path(".github/workflows")
    gitpod: Path = Path(".gitpod.yml")
    pip_constraints: Path = Path(".constraints")
    precommit: Path = Path(".pre-commit-config.yaml")
    prettier: Path = Path(".prettierrc")
    prettier_ignore: Path = Path(".prettierignore")
    pydocstyle: Path = Path(".pydocstyle")
    pyproject: Path = Path("pyproject.toml")
    pytest: Path = Path("pytest.ini")
    setup_cfg: Path = Path("setup.cfg")
    tox: Path = Path("tox.ini")
    vscode_extensions: Path = Path(".vscode/extensions.json")


CONFIG_PATH = _ConfigFilePaths()

REPOMA_DIR = Path(repoma.__file__).parent.absolute()
__README_PATH = "README.md"


def add_badge(badge: str) -> None:
    if not os.path.exists(__README_PATH):
        raise PrecommitError(
            f"This repository contains no {__README_PATH}, so cannot add badge"
        )
    with open(__README_PATH) as stream:
        lines = stream.readlines()
    stripped_lines = set(map(lambda s: s.strip("\n"), lines))
    stripped_lines = set(map(lambda s: s.strip("<br>"), stripped_lines))
    stripped_lines = set(map(lambda s: s.strip("<br />"), stripped_lines))
    if badge not in stripped_lines:
        error_message = f"{__README_PATH} is missing a badge:\n"
        error_message += f"  {badge}\n"
        insert_position = 0
        for insert_position, line in enumerate(lines):  # noqa: B007
            if line.startswith("#"):  # find first Markdown section
                break
        if len(lines) == 0 or insert_position == len(lines) - 1:
            error_message += (
                f"{__README_PATH} contains no title, so cannot add badge"
            )
            raise PrecommitError(error_message)
        lines.insert(insert_position + 1, f"\n{badge}")
        with open(__README_PATH, "w") as stream:
            stream.writelines(lines)
        error_message += "Problem has been fixed."
        raise PrecommitError(error_message)


def remove_badge(badge_pattern: str) -> None:
    if not os.path.exists(__README_PATH):
        raise PrecommitError(
            f"This repository contains no {__README_PATH}, so cannot add badge"
        )
    with open(__README_PATH) as stream:
        lines = stream.readlines()
    badge_line = None
    for line in lines:
        if re.match(badge_pattern, line):
            badge_line = line
            break
    if badge_line is None:
        return
    lines.remove(badge_line)
    with open(__README_PATH, "w") as stream:
        stream.writelines(lines)
    raise PrecommitError(
        f"A badge has been removed from {__README_PATH}:\n\n  {badge_line}"
    )


def copy_config(cfg: ConfigParser) -> ConfigParser:
    # can't use deepcopy in Python 3.6
    # https://stackoverflow.com/a/24343297
    stream = io.StringIO()
    cfg.write(stream)
    stream.seek(0)
    cfg_copy = ConfigParser()
    cfg_copy.read_file(stream)
    return cfg_copy


def extract_config_section(
    extract_from: Union[Path, str],
    extract_to: Union[Path, str],
    sections: List[str],
) -> None:
    cfg = open_config(extract_from)
    if any(map(cfg.has_section, sections)):
        old_cfg, extracted_cfg = __split_config(cfg, sections)
        __write_config(old_cfg, extract_from)
        __write_config(extracted_cfg, extract_to)
        raise PrecommitError(
            f'Section "{", ".join(sections)}"" in "./{CONFIG_PATH.tox}" '
            f'has been extracted to a "./{extract_to}" config file.'
        )


def __split_config(
    cfg: ConfigParser, extracted_sections: List[str]
) -> Tuple[ConfigParser, ConfigParser]:
    old_config = copy_config(cfg)
    extracted_config = copy_config(cfg)
    for section in cfg.sections():
        if section in extracted_sections:
            old_config.remove_section(section)
        else:
            extracted_config.remove_section(section)
    return old_config, extracted_config


def __write_config(cfg: ConfigParser, output_path: Union[Path, str]) -> None:
    with open(output_path, "w") as stream:
        cfg.write(stream)
    format_config(input=output_path, output=output_path)


def format_config(
    input: Union[Path, io.TextIOBase, str],  # noqa: A002
    output: Union[Path, io.TextIOBase, str],
    additional_rules: Optional[Iterable[Callable[[str], str]]] = None,
) -> None:
    content = read(input)
    indent_size = 4
    # replace tabs
    content = content.replace("\t", indent_size * " ")
    # format spaces before comments (two spaces like black does)
    content = re.sub(r"([^\s^\n])[^\S\r\n]+#\s*([^\s])", r"\1  # \2", content)
    # remove trailing white-space
    content = re.sub(r"([^\S\r\n]+)\n", r"\n", content)
    # only two whitelines
    while "\n\n\n" in content:
        content = content.replace("\n\n\n", "\n\n")
    # end file with one and only one newline
    content = content.strip()
    content += "\n"
    if additional_rules is not None:
        for rule in additional_rules:
            content = rule(content)
    write(content, output=output)


def read(input: Union[Path, io.TextIOBase, str]) -> str:  # noqa: A002
    if isinstance(input, (Path, str)):
        with open(input) as input_stream:
            return input_stream.read()
    if isinstance(input, io.TextIOBase):
        return input.read()
    raise TypeError(f"Cannot read from {type(input).__name__}")


def write(content: str, output: Union[Path, io.TextIOBase, str]) -> None:
    if isinstance(output, (Path, str)):
        with open(output, "w") as output_stream:
            output_stream.write(content)
    elif isinstance(output, io.TextIOBase):
        output.write(content)
    else:
        raise TypeError(f"Cannot write from {type(output).__name__}")


def open_config(definition: Union[Path, io.TextIOBase, str]) -> ConfigParser:
    cfg = ConfigParser()
    if isinstance(definition, io.TextIOBase):
        text = definition.read()
        cfg.read_string(text)
    elif isinstance(definition, (Path, str)):
        if isinstance(definition, str):
            path = Path(definition)
        else:
            path = definition
        if not path.exists():
            raise PrecommitError(f'Config file "{path}" does not exist')
        cfg.read(path)
    else:
        raise TypeError(
            f"Cannot create a {ConfigParser.__name__} from a"
            f" {type(definition).__name__}"
        )
    return cfg


def write_config(
    cfg: ConfigParser, output: Union[Path, io.TextIOBase, str]
) -> None:
    if isinstance(output, io.TextIOBase):
        cfg.write(output)
    elif isinstance(output, (Path, str)):
        with open(output) as stream:
            cfg.write(stream)
    else:
        raise TypeError(
            f"Cannot write a {ConfigParser.__name__} to a"
            f" {type(output).__name__}"
        )


def get_supported_python_versions() -> List[str]:
    """Extract supported Python versions from package classifiers.

    >>> get_supported_python_versions()
    ['3.6', '3.7', '3.8', '3.9', '3.10']
    """
    cfg = open_setup_cfg()
    if not cfg.has_option("metadata", "classifiers"):
        raise PrecommitError(
            "This package does not have Python version classifiers."
            " See https://pypi.org/classifiers."
        )
    raw = cfg.get("metadata", "classifiers")
    lines = raw.split("\n")
    lines = list(map(lambda s: s.strip(), lines))
    identifier = "Programming Language :: Python :: 3."
    classifiers = list(filter(lambda s: s.startswith(identifier), lines))
    if not classifiers:
        raise PrecommitError(
            "setup.cfg does not have any classifiers of the form"
            f' "{identifier}*"'
        )
    prefix = identifier[:-2]
    return list(map(lambda s: s.replace(prefix, ""), classifiers))


def get_repo_url() -> str:
    cfg = open_setup_cfg()
    if not cfg.has_section("metadata"):
        raise PrecommitError("setup.cfg does not contain a metadata section")
    project_urls_def = cfg["metadata"].get("project_urls", None)
    if project_urls_def is None:
        error_message = (
            "Section metadata in setup.cfg does not contain project_urls."
            " Should be something like:\n\n"
            "[metadata]\n"
            "...\n"
            "project_urls =\n"
            "    Tracker = https://github.com/ComPWA/ampform/issues\n"
            "    Source = https://github.com/ComPWA/ampform\n"
            "    ...\n"
        )
        raise PrecommitError(error_message)
    project_url_lines = project_urls_def.split("\n")
    project_url_lines = list(
        filter(lambda line: line.strip(), project_url_lines)
    )
    project_urls = {}
    for line in project_url_lines:
        url_type, url, *_ = tuple(line.split("="))
        url_type = url_type.strip()
        url = url.strip()
        project_urls[url_type] = url
    source_url = project_urls.get("Source")
    if source_url is None:
        raise PrecommitError(
            'metadata.project_urls in setup.cfg does not contain "Source" URL'
        )
    return source_url


def open_setup_cfg() -> ConfigParser:
    if not CONFIG_PATH.setup_cfg.exists():
        raise PrecommitError("This repository contains no setup.cfg file")
    return open_config(CONFIG_PATH.setup_cfg)


def rename_config(old: str, new: str) -> None:
    if os.path.exists(old):
        os.rename(old, new)
        raise PrecommitError(f"File {old} has been renamed to {new}")


def add_vscode_extension_recommendation(extension_name: str) -> None:
    if not CONFIG_PATH.vscode_extensions.exists():
        CONFIG_PATH.vscode_extensions.parent.mkdir(exist_ok=True)
        config = {}
    else:
        with open(CONFIG_PATH.vscode_extensions) as stream:
            config = json.load(stream)
    recommended_extensions = config.get("recommendations", [])
    if extension_name not in set(recommended_extensions):
        recommended_extensions.append(extension_name)
        config["recommendations"] = recommended_extensions
        __dump_vscode_config(config)
        raise PrecommitError(
            f'Added VSCode extension recommendation "{extension_name}"'
        )


def remove_vscode_extension_recommendation(extension_name: str) -> None:
    if not CONFIG_PATH.vscode_extensions.exists():
        return
    with open(CONFIG_PATH.vscode_extensions) as stream:
        config = json.load(stream)
    recommended_extensions = list(config.get("recommendations", []))
    if extension_name in recommended_extensions:
        recommended_extensions.remove(extension_name)
        config["recommendations"] = recommended_extensions
        __dump_vscode_config(config)
        raise PrecommitError(
            f'Removed VSCode extension recommendation "{extension_name}"'
        )


def __dump_vscode_config(config: dict) -> None:
    with open(CONFIG_PATH.vscode_extensions, "w") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")


def write_script(content: str, path: Union[Path, str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as stream:
        stream.write(content)


class _IncreasedYamlIndent(yaml.Dumper):
    # pylint: disable=too-many-ancestors
    def increase_indent(
        self, flow: bool = False, indentless: bool = False
    ) -> None:
        return super().increase_indent(flow, False)

    def write_line_break(self, data: Optional[str] = None) -> None:
        """See https://stackoverflow.com/a/44284819."""
        super().write_line_break(data)
        if len(self.indents) == 1:
            super().write_line_break()


def create_prettier_round_trip_yaml() -> YAML:
    yaml_parser = YAML(typ="rt")
    yaml_parser.preserve_quotes = True  # type: ignore[assignment]
    yaml_parser.map_indent = 2  # type: ignore[assignment]
    yaml_parser.indent = 4
    yaml_parser.block_seq_indent = 2
    return yaml_parser


def load_round_trip_precommit_config(
    path: Path = CONFIG_PATH.precommit,
) -> Tuple[dict, YAML]:
    yaml_parser = create_prettier_round_trip_yaml()
    config = yaml_parser.load(path)
    return config, yaml_parser


def write_yaml(definition: dict, output_path: Union[Path, str]) -> None:
    """Write a `dict` to disk with standardized YAML formatting."""
    with open(output_path, "w") as stream:
        yaml.dump(
            definition,
            stream,
            sort_keys=False,
            Dumper=_IncreasedYamlIndent,
            default_flow_style=False,
        )


def natural_sorting(text: str) -> List[Union[float, str]]:
    # https://stackoverflow.com/a/5967539/13219025
    return [
        __attempt_number_cast(c)
        for c in re.split(r"[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)", text)
    ]


def __attempt_number_cast(text: str) -> Union[float, str]:
    try:
        return float(text)
    except ValueError:
        return text


class PrecommitCi(BaseModel):
    """https://pre-commit.ci/#configuration."""

    autofix_commit_msg: str = "[pre-commit.ci] auto fixes [...]"
    autofix_prs: bool = True
    autoupdate_commit_msg: str = "[pre-commit.ci] pre-commit autoupdate"
    autoupdate_schedule: str = "weekly"
    skip: List[str] = []
    submodules: bool = False


class Hook(BaseModel):
    """https://pre-commit.com/#pre-commit-configyaml---hooks."""

    id: str  # noqa: A003
    args: List[str] = []
    name: Optional[str] = None
    files: Optional[str] = None
    exclude: Optional[str] = None
    types: Optional[List[str]] = None
    alias: Optional[str] = None


class Repo(BaseModel):
    """https://pre-commit.com/#pre-commit-configyaml---repos."""

    repo: str
    rev: Optional[str] = None
    hooks: List[Hook]

    def get_hook_index(self, hook_id: str) -> Optional[int]:
        for i, hook in enumerate(self.hooks):
            if hook.id == hook_id:
                return i
        return None


class PrecommitConfig(BaseModel):
    """https://pre-commit.com/#pre-commit-configyaml---top-level."""

    repos: List[Repo]
    ci: Optional[PrecommitCi] = None
    files: str = ""
    exclude: str = "^$"
    fail_fast: bool = False

    @classmethod
    def load(
        cls, path: Union[Path, str] = CONFIG_PATH.precommit
    ) -> "PrecommitConfig":
        if not os.path.exists(path):
            raise PrecommitError(f"This repository contains no {path}")
        with open(path) as stream:
            definition = yaml.safe_load(stream)
        return PrecommitConfig(**definition)

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