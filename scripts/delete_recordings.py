"""Delete recorded samples (withdrawal or cleanup). Dry run unless --yes.

    uv run python scripts/delete_recordings.py --signer DEV-01            # list what would go
    uv run python scripts/delete_recordings.py --signer DEV-01 --yes      # delete
    uv run python scripts/delete_recordings.py --session S20261018-... --reason cleanup --yes
    uv run python scripts/delete_recordings.py --sample S20261018-...-003 --yes

Removes each .npz and appends a tombstone to manifests/tombstones.jsonl, so the
sample disappears from reviews, reports and training. For a withdrawal, also
update the identity register (kept outside DATA_ROOT) and exclude the signer from
the next model release (docs/DATASET_AND_ANNOTATION.md §8).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _dataset import resolve_data_root

from vsl_features.dataset import Dataset, TombstoneReason


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--signer", help="pseudonymous signer ID, e.g. DEV-01")
    target.add_argument("--session", help="session ID")
    target.add_argument("--sample", help="sample ID")
    parser.add_argument("--reason", choices=["withdrawal", "cleanup", "rejected"])
    parser.add_argument(
        "--data-root", type=Path, help="defaults to VSL_DATA_ROOT / the user data dir"
    )
    parser.add_argument("--yes", action="store_true", help="actually delete (default: dry run)")
    args = parser.parse_args(argv)

    root = resolve_data_root(args.data_root)
    dataset = Dataset(root)
    views = [
        v
        for v in dataset.samples()
        if (args.signer and v.record.signer_id == args.signer)
        or (args.session and v.record.session_id == args.session)
        or (args.sample and v.record.sample_id == args.sample)
    ]
    if not views:
        print("nothing to delete")
        return 0
    reason: TombstoneReason = args.reason or ("withdrawal" if args.signer else "cleanup")
    print(f"{len(views)} sample(s) in {root}:")
    for v in views:
        print(f"  {v.record.sample_id}  {v.label:<12} {v.status}")
    if not args.yes:
        print("\ndry run: nothing deleted. Re-run with --yes to delete.")
        return 0
    deleted = sum(dataset.delete_sample(v.record.sample_id, reason) for v in views)
    # Remove directories left empty by the deletion.
    for v in views:
        folder = (root / v.record.file).parent
        for directory in (folder, folder.parent):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    print(f"\ndeleted {deleted} sample(s); tombstones recorded (reason: {reason}).")
    if reason == "withdrawal":
        print(
            "Also update the identity register and exclude this signer from the next model release."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
