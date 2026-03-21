"""Parse dependency files into (ecosystem, package_name) pairs."""

import json
import re
from pathlib import Path
from typing import List, Tuple


def parse_requirements_txt(path: Path) -> List[Tuple[str, str]]:
    """Parse requirements.txt / requirements-dev.txt etc."""
    results = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip version specifiers, extras, environment markers
        name = re.split(r"[>=<!\[;@\s]", line)[0].strip()
        if name:
            results.append(("pypi", name))
    return results


def parse_pyproject_toml(path: Path) -> List[Tuple[str, str]]:
    """Parse pyproject.toml dependencies. Minimal TOML parser -- just grabs dep lines."""
    results = []
    text = path.read_text()
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("[project.dependencies]", "dependencies = ["):
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("[") or (stripped and not stripped.startswith('"') and not stripped.startswith("'")):
                if stripped == "]":
                    in_deps = False
                    continue
                if stripped.startswith("["):
                    in_deps = False
                    continue
            # Extract package name from "package>=1.0"
            match = re.match(r'["\']([a-zA-Z0-9_.-]+)', stripped)
            if match:
                results.append(("pypi", match.group(1)))
    return results


def parse_package_json(path: Path) -> List[Tuple[str, str]]:
    """Parse package.json dependencies + devDependencies."""
    results = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return results
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(key, {})
        if isinstance(deps, dict):
            for name in deps:
                results.append(("npm", name))
    return results


def parse_cargo_toml(path: Path) -> List[Tuple[str, str]]:
    """Parse Cargo.toml [dependencies]."""
    results = []
    in_deps = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]" or stripped == "[dev-dependencies]":
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps and "=" in stripped:
            name = stripped.split("=")[0].strip()
            if name and not name.startswith("#"):
                results.append(("crates.io", name))
    return results


def parse_go_mod(path: Path) -> List[Tuple[str, str]]:
    """Parse go.mod require block."""
    results = []
    in_require = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if stripped == ")" and in_require:
            in_require = False
            continue
        if in_require:
            # Lines look like: github.com/foo/bar v1.2.3
            parts = stripped.split()
            if parts and not parts[0].startswith("//"):
                results.append(("go", parts[0]))
        elif stripped.startswith("require "):
            # Single-line require
            parts = stripped.split()
            if len(parts) >= 2:
                results.append(("go", parts[1]))
    return results


# Map filenames to parsers
FILE_PARSERS = {
    "requirements.txt": parse_requirements_txt,
    "requirements-dev.txt": parse_requirements_txt,
    "requirements_dev.txt": parse_requirements_txt,
    "pyproject.toml": parse_pyproject_toml,
    "package.json": parse_package_json,
    "Cargo.toml": parse_cargo_toml,
    "go.mod": parse_go_mod,
}


def auto_detect(directory: Path) -> List[Tuple[str, str]]:
    """Scan a directory for known dependency files and parse them all."""
    results = []
    for filename, parser in FILE_PARSERS.items():
        filepath = directory / filename
        if filepath.exists():
            results.extend(parser(filepath))
    return results
