#!/usr/bin/env python3
"""
Sync card tier metadata from images/ folder structure into MongoDB cards collection.

What this script does:
- Scans images/<tier>/<card_id>.<ext>
- Derives each card's tier from the folder name
- Upserts {tier, tier_source, tier_synced_at} to cards collection

Safety features:
- Dry-run mode
- Conflict handling for duplicate card IDs across multiple tiers
- Optional stale-tier cleanup for DB docs not present in images
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne


DEFAULT_TIER_PRIORITY = ["common", "rare", "epic", "legendary", "mystic", "celestial"]
VALID_IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif"}


@dataclass
class ScanResult:
    card_tiers: Dict[str, str] = field(default_factory=dict)
    conflicts: List[Tuple[str, str, str]] = field(default_factory=list)
    skipped_files: int = 0
    scanned_files: int = 0


@dataclass
class SyncResult:
    unchanged: int = 0
    inserted: int = 0
    updated: int = 0
    stale_cleared: int = 0
    bulk_ops: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync card tiers from images folders to MongoDB cards collection"
    )
    parser.add_argument(
        "--images-dir",
        default="images",
        help="Path to images root folder (default: images)",
    )
    parser.add_argument(
        "--mongo-url",
        default=None,
        help="MongoDB URL. Defaults to MONGODB_URL from .env",
    )
    parser.add_argument(
        "--mongo-db",
        default=None,
        help="MongoDB database name. Defaults to MONGODB_NAME from .env",
    )
    parser.add_argument(
        "--mongo-collection",
        default="cards",
        help="MongoDB collection name (default: cards)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to env file (default: .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to MongoDB",
    )
    parser.add_argument(
        "--clear-stale-tier",
        action="store_true",
        help="Unset tier for DB docs not present in images scan",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="MongoDB bulk write batch size (default: 1000)",
    )
    parser.add_argument(
        "--tier-priority",
        default=",".join(DEFAULT_TIER_PRIORITY),
        help=(
            "Comma-separated tier conflict priority. "
            "Earlier wins when same card ID appears in multiple folders"
        ),
    )
    return parser.parse_args()


def resolve_tier_priority(priority_csv: str) -> List[str]:
    tiers = [part.strip().lower() for part in priority_csv.split(",") if part.strip()]
    if not tiers:
        return DEFAULT_TIER_PRIORITY.copy()
    return tiers


def choose_tier(existing: str, candidate: str, tier_priority: List[str]) -> str:
    rank = {tier: i for i, tier in enumerate(tier_priority)}
    existing_rank = rank.get(existing, 10_000)
    candidate_rank = rank.get(candidate, 10_000)
    return existing if existing_rank <= candidate_rank else candidate


def scan_images(images_root: Path, tier_priority: List[str]) -> ScanResult:
    result = ScanResult()

    if not images_root.exists() or not images_root.is_dir():
        raise FileNotFoundError(f"images directory not found: {images_root}")

    tier_dirs = [p for p in images_root.iterdir() if p.is_dir() and not p.name.startswith(".")]

    for tier_dir in sorted(tier_dirs, key=lambda p: p.name.lower()):
        tier = tier_dir.name.lower()

        for file_path in tier_dir.iterdir():
            if file_path.name.startswith("."):
                continue
            if not file_path.is_file():
                continue

            result.scanned_files += 1

            if file_path.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
                result.skipped_files += 1
                continue

            card_id = file_path.stem.strip()
            if not card_id:
                result.skipped_files += 1
                continue

            existing_tier = result.card_tiers.get(card_id)
            if existing_tier and existing_tier != tier:
                chosen_tier = choose_tier(existing_tier, tier, tier_priority)
                if chosen_tier != existing_tier:
                    result.card_tiers[card_id] = chosen_tier
                result.conflicts.append((card_id, existing_tier, tier))
            else:
                result.card_tiers[card_id] = tier

    return result


async def flush_bulk(collection, ops: List[UpdateOne], dry_run: bool) -> None:
    if not ops:
        return
    if dry_run:
        return
    await collection.bulk_write(ops, ordered=False)


async def sync_tiers(
    collection,
    card_tiers: Dict[str, str],
    dry_run: bool,
    clear_stale_tier: bool,
    batch_size: int,
) -> SyncResult:
    result = SyncResult()

    existing_tiers: Dict[str, str] = {}
    async for doc in collection.find({}, {"_id": 1, "tier": 1}):
        existing_tiers[str(doc["_id"])] = doc.get("tier")

    now_ts = int(time.time())
    ops: List[UpdateOne] = []

    for card_id, derived_tier in card_tiers.items():
        existing_tier = existing_tiers.get(card_id)

        if existing_tier == derived_tier:
            result.unchanged += 1
            continue

        if card_id in existing_tiers:
            result.updated += 1
        else:
            result.inserted += 1

        ops.append(
            UpdateOne(
                {"_id": card_id},
                {
                    "$set": {
                        "tier": derived_tier,
                        "tier_source": "images_sync",
                        "tier_synced_at": now_ts,
                    }
                },
                upsert=True,
            )
        )

        if len(ops) >= batch_size:
            result.bulk_ops += len(ops)
            await flush_bulk(collection, ops, dry_run)
            ops.clear()

    if clear_stale_tier:
        for card_id, existing_tier in existing_tiers.items():
            if card_id in card_tiers:
                continue
            if existing_tier is None:
                continue

            result.stale_cleared += 1
            ops.append(
                UpdateOne(
                    {"_id": card_id},
                    {
                        "$unset": {"tier": ""},
                        "$set": {
                            "tier_source": "images_sync",
                            "tier_synced_at": now_ts,
                        },
                    },
                )
            )

            if len(ops) >= batch_size:
                result.bulk_ops += len(ops)
                await flush_bulk(collection, ops, dry_run)
                ops.clear()

    if ops:
        result.bulk_ops += len(ops)
        await flush_bulk(collection, ops, dry_run)

    return result


def print_summary(
    scan_result: ScanResult,
    sync_result: SyncResult,
    dry_run: bool,
    clear_stale_tier: bool,
) -> None:
    print("\n=== Card Tier Sync Summary ===")
    print(f"Scanned files:        {scan_result.scanned_files}")
    print(f"Skipped files:        {scan_result.skipped_files}")
    print(f"Unique card IDs:      {len(scan_result.card_tiers)}")
    print(f"Conflicts detected:   {len(scan_result.conflicts)}")

    if scan_result.conflicts:
        print("Conflict samples (card_id: tier_a vs tier_b):")
        for card_id, tier_a, tier_b in scan_result.conflicts[:10]:
            print(f"  - {card_id}: {tier_a} vs {tier_b}")
        if len(scan_result.conflicts) > 10:
            print(f"  ... and {len(scan_result.conflicts) - 10} more")

    mode = "DRY-RUN" if dry_run else "WRITE"
    print(f"Mode:                 {mode}")
    print(f"Tier unchanged:       {sync_result.unchanged}")
    print(f"Tier inserted:        {sync_result.inserted}")
    print(f"Tier updated:         {sync_result.updated}")
    print(f"Stale tier cleared:   {sync_result.stale_cleared if clear_stale_tier else 0}")
    print(f"Bulk operations:      {sync_result.bulk_ops}")


async def run(args: argparse.Namespace) -> int:
    load_dotenv(args.env_file)

    mongo_url = args.mongo_url or os.getenv("MONGODB_URL")
    mongo_db = args.mongo_db or os.getenv("MONGODB_NAME")

    if not mongo_url or not mongo_db:
        print("Missing MongoDB config. Set MONGODB_URL and MONGODB_NAME (or pass --mongo-url/--mongo-db).")
        return 2

    tier_priority = resolve_tier_priority(args.tier_priority)
    images_root = Path(args.images_dir).resolve()

    scan_result = scan_images(images_root, tier_priority)

    client = AsyncIOMotorClient(host=mongo_url, serverSelectionTimeoutMS=10_000)
    try:
        await client.server_info()
        collection = client[mongo_db][args.mongo_collection]

        sync_result = await sync_tiers(
            collection=collection,
            card_tiers=scan_result.card_tiers,
            dry_run=args.dry_run,
            clear_stale_tier=args.clear_stale_tier,
            batch_size=max(1, args.batch_size),
        )

        print_summary(
            scan_result=scan_result,
            sync_result=sync_result,
            dry_run=args.dry_run,
            clear_stale_tier=args.clear_stale_tier,
        )
        return 0
    finally:
        client.close()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2
    except KeyboardInterrupt:
        print("\nCanceled by user")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
