#!/usr/bin/env python3

"""
scanner.py

Polls a shared S3 bucket for an artifact manifest.

Workflow:

1. Check whether packagefile.yaml exists in the S3 bucket.
2. If it does not exist, wait for the configured polling interval.
3. If it exists, create a scheduling marker/job file under:

       s3://split-env-data/scheduling/scheduling-jobs

The polling interval is configurable through the POLL_INTERVAL_SECONDS
environment variable. The default is 300 seconds (5 minutes).
"""

import os
import subprocess
import time
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

S3_BUCKET = "split-env-data"

# File produced by test-env1.
MANIFEST_KEY = "packagefile.yaml"

# Object to create after detecting the manifest.
SCHEDULING_KEY = "scheduling/scheduling-jobs"

# Default polling interval = 5 minutes.
POLL_INTERVAL_SECONDS = int(
    os.getenv("POLL_INTERVAL_SECONDS", "300")
)


# ---------------------------------------------------------------------------
# S3 operations
# ---------------------------------------------------------------------------

def manifest_exists() -> bool:
    """
    Check whether packagefile.yaml exists in S3.

    head-object checks object metadata without downloading the object.
    """

    result = subprocess.run(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            S3_BUCKET,
            "--key",
            MANIFEST_KEY,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return result.returncode == 0


def create_scheduling_job() -> None:
    """
    Create the scheduling marker object in S3.

    S3 uses object key prefixes rather than traditional directories,
    so writing scheduling/scheduling-jobs automatically creates the
    scheduling/ hierarchy shown in the S3 console.
    """

    timestamp = datetime.now(timezone.utc).isoformat()

    content = (
        f"source_manifest: {MANIFEST_KEY}\n"
        f"status: scheduled\n"
        f"created_at: {timestamp}\n"
    )

    subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            "-",
            f"s3://{S3_BUCKET}/{SCHEDULING_KEY}",
        ],
        input=content,
        text=True,
        check=True,
    )

    print(
        f"Scheduling job created: "
        f"s3://{S3_BUCKET}/{SCHEDULING_KEY}"
    )


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Continuously poll S3 for the producer manifest."""

    print("=" * 60)
    print("test-env2 S3 Scanner")
    print("=" * 60)
    print(f"S3 bucket      : s3://{S3_BUCKET}")
    print(f"Watching for   : {MANIFEST_KEY}")
    print(f"Polling every  : {POLL_INTERVAL_SECONDS} seconds")
    print()

    while True:

        print(
            f"[{datetime.now(timezone.utc).isoformat()}] "
            f"Checking for {MANIFEST_KEY}..."
        )

        if manifest_exists():

            print(f"Detected manifest: {MANIFEST_KEY}")

            create_scheduling_job()

            print("Scheduling completed.")
            break

        print(
            f"Manifest not found. "
            f"Checking again in {POLL_INTERVAL_SECONDS} seconds..."
        )

        time.sleep(POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()