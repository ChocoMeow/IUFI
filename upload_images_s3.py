#!/usr/bin/env python3
"""
Upload local card art under images/ to S3, preserving images/<tier>/<file>.

Designed to re-run after new cards are ingested: existing S3 keys are skipped
unless --force is set.

Credentials come from the default AWS chain (environment, shared config, or IAM).
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Set

import boto3
from botocore.exceptions import BotoCoreError, ClientError


DEFAULT_BUCKET = "iufi-prod"
DEFAULT_PREFIX = "images/"
IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif"}


@dataclass
class UploadStats:
    scanned: int = 0
    skipped_existing: int = 0
    skipped_ext: int = 0
    uploaded: int = 0
    failed: int = 0
    would_upload: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload images/<tier>/ files to s3://<bucket>/images/<tier>/"
    )
    parser.add_argument(
        "--images-dir",
        default="images",
        help="Local images root (default: images)",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"S3 bucket name (default: {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"S3 key prefix (default: {DEFAULT_PREFIX})",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        help="AWS region. Defaults to AWS_REGION / AWS_DEFAULT_REGION / boto3 default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be uploaded without writing to S3",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload even when the S3 key already exists",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help="AWS shared-credentials profile name",
    )
    return parser.parse_args()


def normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip().lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def local_files(images_dir: Path) -> Iterable[Path]:
    for path in sorted(images_dir.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            yield path


def s3_key_for(images_dir: Path, file_path: Path, prefix: str) -> str:
    relative = file_path.relative_to(images_dir).as_posix()
    return f"{prefix}{relative}"


def list_existing_keys(s3_client, bucket: str, prefix: str) -> Set[str]:
    keys: Set[str] = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def main() -> int:
    args = parse_args()
    images_dir = Path(args.images_dir).resolve()
    prefix = normalize_prefix(args.prefix)

    if not images_dir.is_dir():
        print(f"Images directory not found: {images_dir}", file=sys.stderr)
        return 1

    session_kwargs = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    if args.region:
        session_kwargs["region_name"] = args.region

    session = boto3.Session(**session_kwargs)
    s3 = session.client("s3")
    stats = UploadStats()

    try:
        existing = set() if args.force else list_existing_keys(s3, args.bucket, prefix)
    except (BotoCoreError, ClientError) as exc:
        print(f"Failed to list s3://{args.bucket}/{prefix}: {exc}", file=sys.stderr)
        return 1

    print(
        f"Local: {images_dir} → s3://{args.bucket}/{prefix} "
        f"({len(existing)} existing keys, force={args.force}, dry_run={args.dry_run})"
    )

    for file_path in local_files(images_dir):
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            stats.skipped_ext += 1
            continue

        stats.scanned += 1
        key = s3_key_for(images_dir, file_path, prefix)

        if not args.force and key in existing:
            stats.skipped_existing += 1
            continue

        if args.dry_run:
            stats.would_upload.append(key)
            continue

        extra = {"ContentType": content_type_for(file_path)}
        try:
            s3.upload_file(str(file_path), args.bucket, key, ExtraArgs=extra)
        except (BotoCoreError, ClientError) as exc:
            stats.failed += 1
            print(f"FAIL {key}: {exc}", file=sys.stderr)
            continue

        stats.uploaded += 1
        if stats.uploaded % 50 == 0:
            print(f"Uploaded {stats.uploaded} new files...")

    if args.dry_run:
        print(f"Would upload {len(stats.would_upload)} files:")
        for key in stats.would_upload:
            print(f"  {key}")
    else:
        print(f"Uploaded {stats.uploaded} files.")

    print(
        f"Done. scanned={stats.scanned} skipped_existing={stats.skipped_existing} "
        f"skipped_ext={stats.skipped_ext} uploaded={stats.uploaded} failed={stats.failed}"
    )
    return 1 if stats.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
