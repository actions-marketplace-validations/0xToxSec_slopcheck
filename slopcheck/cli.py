"""CLI entry point. Zero config, blunt output."""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from slopcheck.registries import REGISTRY_CHECKERS, PackageInfo
from slopcheck.detect import analyze, Verdict
from slopcheck.parsers import auto_detect, FILE_PARSERS


# ---------------------------------------------------------------------------
# Colors (ANSI) -- vibe coders deserve pretty output
# ---------------------------------------------------------------------------

class C:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _status_badge(status: str) -> str:
    if status == "SLOP":
        return f"{C.RED}{C.BOLD}[SLOP]{C.RESET}"
    elif status == "SUS":
        return f"{C.YELLOW}{C.BOLD}[SUS]{C.RESET}"
    else:
        return f"{C.GREEN}[OK]{C.RESET}"


def _severity_color(severity: str) -> str:
    if severity == "critical":
        return C.RED
    elif severity == "warning":
        return C.YELLOW
    return C.DIM


def print_verdict(v: Verdict) -> None:
    """Print one package's verdict. Blunt."""
    badge = _status_badge(v.status)
    print(f"\n  {badge} {C.BOLD}{v.package}{C.RESET} {C.DIM}({v.ecosystem}){C.RESET}")

    for flag in v.flags:
        color = _severity_color(flag.severity)
        print(f"    {color}> {flag.message}{C.RESET}")

    if v.suggestion:
        print(f"    {C.CYAN}? Did you mean: {C.BOLD}{v.suggestion}{C.RESET}")


def print_summary(verdicts: List[Verdict]) -> None:
    """Print final tally."""
    slop = sum(1 for v in verdicts if v.status == "SLOP")
    sus = sum(1 for v in verdicts if v.status == "SUS")
    ok = sum(1 for v in verdicts if v.status == "OK")
    total = len(verdicts)

    print(f"\n{'='*50}")
    print(f"  scanned {total} packages")
    if slop:
        print(f"  {C.RED}{C.BOLD}{slop} SLOP{C.RESET} -- hallucinated or dangerously new")
    if sus:
        print(f"  {C.YELLOW}{C.BOLD}{sus} SUS{C.RESET} -- worth a second look")
    if ok:
        print(f"  {C.GREEN}{ok} OK{C.RESET}")
    print()


def _check_one(ecosystem: str, name: str) -> Verdict:
    """Check a single package against its registry and return a verdict."""
    checker = REGISTRY_CHECKERS.get(ecosystem)
    if not checker:
        # Unknown ecosystem -- just flag it
        info = PackageInfo(name=name, ecosystem=ecosystem, exists=False, error="unknown registry")
        return analyze(info)
    info = checker(name)
    return analyze(info)


def _scan_directory(directory: Path) -> List[Tuple[str, str]]:
    """Find and parse all dependency files in a directory."""
    deps = auto_detect(directory)
    if not deps:
        print(f"{C.YELLOW}No dependency files found in {directory}{C.RESET}")
        print(f"Looking for: {', '.join(FILE_PARSERS.keys())}")
        sys.exit(1)
    return deps


def _scan_file(filepath: Path) -> List[Tuple[str, str]]:
    """Parse a specific dependency file."""
    name = filepath.name
    parser = FILE_PARSERS.get(name)
    if not parser:
        # Try matching partial names (e.g., requirements-custom.txt)
        if "requirements" in name and name.endswith(".txt"):
            from slopcheck.parsers import parse_requirements_txt
            parser = parse_requirements_txt
        else:
            print(f"{C.RED}Don't know how to parse: {name}{C.RESET}")
            print(f"Supported: {', '.join(FILE_PARSERS.keys())}")
            sys.exit(1)
    return parser(filepath)


def main():
    parser = argparse.ArgumentParser(
        prog="slopcheck",
        description="Detect AI-hallucinated packages before you install them.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Directory to scan, a dependency file, or a package name (with --pkg)",
    )
    parser.add_argument(
        "--pkg",
        metavar="ECOSYSTEM",
        choices=["pypi", "npm", "crates.io", "go"],
        help="Check a single package. Specify ecosystem: pypi, npm, crates.io, go",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Parallel workers for registry checks (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    # Mode 1: Single package check
    if args.pkg:
        print(f"\n{C.BOLD}slopcheck{C.RESET} checking {args.target} on {args.pkg}...")
        verdict = _check_one(args.pkg, args.target)
        if args.json_output:
            _print_json([verdict])
        else:
            print_verdict(verdict)
            print()
        sys.exit(2 if verdict.status == "SLOP" else 1 if verdict.status == "SUS" else 0)

    # Mode 2: Scan file or directory
    target = Path(args.target)
    if target.is_file():
        deps = _scan_file(target)
        print(f"\n{C.BOLD}slopcheck{C.RESET} scanning {target.name}...")
    else:
        deps = _scan_directory(target)
        print(f"\n{C.BOLD}slopcheck{C.RESET} scanning {target.resolve()}...")

    # Deduplicate
    deps = list(set(deps))
    print(f"  found {len(deps)} dependencies\n")

    # Check all packages in parallel
    verdicts: List[Verdict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_check_one, eco, name): (eco, name)
            for eco, name in deps
        }
        for future in as_completed(futures):
            verdict = future.result()
            verdicts.append(verdict)
            if not args.json_output:
                print_verdict(verdict)

    # Sort: worst first
    order = {"SLOP": 0, "SUS": 1, "OK": 2}
    verdicts.sort(key=lambda v: order.get(v.status, 3))

    if args.json_output:
        _print_json(verdicts)
    else:
        print_summary(verdicts)

    # Exit code: 2 if any slop, 1 if any sus, 0 if clean
    if any(v.status == "SLOP" for v in verdicts):
        sys.exit(2)
    elif any(v.status == "SUS" for v in verdicts):
        sys.exit(1)
    sys.exit(0)


def _print_json(verdicts: List[Verdict]) -> None:
    """JSON output for CI integration."""
    import json
    output = []
    for v in verdicts:
        output.append({
            "package": v.package,
            "ecosystem": v.ecosystem,
            "status": v.status,
            "flags": [{"signal": f.signal, "severity": f.severity, "message": f.message} for f in v.flags],
            "suggestion": v.suggestion,
        })
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
