#!/usr/bin/env python3
"""Prepare runner routing in local checkouts. Never publishes or sets variables.

Usage: python3 scripts/route-runners.py [--write] /path/to/repo ...
Default prints a diff. Repeated --write is a no-op. Existing AWS labels remain
fallbacks until the optional org variables are enabled after a live canary.
"""
import argparse
import difflib
import re
from pathlib import Path

HOSTED = "(github.event.repository.private == false || vars.KORZ_RUNNER_BACKEND == 'github')"


def transform(text):
    job = None
    result = []
    for line in text.splitlines(keepends=True):
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            job = match.group(1)
        if job == "sast" and re.match(r"^    container: semgrep/semgrep:", line):
            continue
        if line.startswith("    runs-on: ${{ ") and "KORZ_RUNNER_BACKEND" not in line:
            expr = line.strip().removeprefix("runs-on: ${{ ").removesuffix(" }}")
            # Native Semgrep and tiny orchestration jobs can use cheaper AWS
            # profiles. Real Docker jobs keep their existing CodeBuild routing.
            if job == "sast":
                expr = "vars.KORZ_SECURITY_RUNNER_LABELS != '' && fromJSON(vars.KORZ_SECURITY_RUNNER_LABELS) || " + expr
            elif job in {"gate", "changes", "update-tfvars"}:
                expr = "vars.KORZ_UTILITY_RUNNER_LABELS != '' && fromJSON(vars.KORZ_UTILITY_RUNNER_LABELS) || " + expr
            # Arm64 builds must remain Arm64; migrate them explicitly instead.
            if "arm" in expr.lower():
                result.append(line)
                continue
            line = "    runs-on: ${{ " + HOSTED + " && 'ubuntu-latest' || " + expr + " }}\n"
        result.append(line)
    return "".join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("repos", nargs="+", type=Path)
    args = parser.parse_args()
    for repo in args.repos:
        directory = repo / ".github/workflows"
        if not directory.is_dir():
            parser.error(f"Not a workflow checkout: {repo}")
        supported = {"security.yml", "build-docker-ecr.yml", "ci-go.yml", "ci-dotnet.yml", "ci-node.yml", "ci-python.yml"}
        for path in sorted(directory.glob("*.yml")):
            if path.name not in supported:
                continue
            original = path.read_text()
            changed = transform(original)
            if original == changed:
                continue
            print("".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile=str(path), tofile=str(path))), end="")
            if args.write:
                path.write_text(changed)


if __name__ == "__main__":
    main()
