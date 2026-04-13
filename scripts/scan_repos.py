"""Batch-scan multiple repositories and persist normalized outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.batch import batch_scans_dir, read_manifest, scan_repo_to_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-scan repository paths with Depsly.")
    parser.add_argument("repo_paths", nargs="*", help="Repository paths to scan.")
    parser.add_argument("--manifest", type=Path, help="Optional manifest file with one repo path per line.")
    parser.add_argument("--output-dir", type=Path, default=batch_scans_dir(), help="Directory for output JSON files.")
    parser.add_argument("--limit", type=int, default=10, help="Max recommendations per saved scan.")
    parser.add_argument("--no-dev", action="store_true", help="Exclude devDependencies.")
    parser.add_argument("--dry-run", action="store_true", help="Print intended actions without writing files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_paths = [Path(path).expanduser() for path in args.repo_paths]
    if args.manifest:
        repo_paths.extend(read_manifest(args.manifest))

    if not repo_paths:
        print("No repo paths provided.")
        return 1

    saved = 0
    skipped = 0
    failed = 0

    for repo_path in repo_paths:
        try:
            result = scan_repo_to_output(
                repo_path,
                output_dir=args.output_dir,
                include_dev=not args.no_dev,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            failed += 1
            print(f"FAIL {repo_path} | {exc}")
            continue

        if result["status"] in {"saved", "dry_run"}:
            saved += 1
            print(f"{result['status'].upper()} {result['repo']} -> {result['output']}")
        else:
            skipped += 1
            print(f"SKIP {result['repo']} | {result['reason']}")

    print("")
    print(f"Summary: saved={saved} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
