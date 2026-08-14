#!/usr/bin/env python3

"""
scanner.py

Scans the shared S3 bucket for incoming artifact submissions.

The producer (test-env1) publishes submissions using:

    incoming/<job-id>/packagefile.bin
    incoming/<job-id>/packagefile.yaml

The presence of packagefile.yaml indicates that the producer has
finished publishing the submission.

This script performs ONE scan and then exits.

GitHub Actions is responsible for running this script periodically
(every 5 minutes).
"""

import subprocess
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

S3_BUCKET = "split-env-data"

# Prefix where test-env1 publishes new submissions.
INCOMING_PREFIX = "incoming/"

# Manifest filename used as the submission-ready signal.
MANIFEST_NAME = "packagefile.yaml"

# Prefix where scheduling records will be created.
SCHEDULING_PREFIX = "scheduling/"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def current_timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# S3 operations
# ---------------------------------------------------------------------------

def find_incoming_manifests() -> list[str]:
    """
    Find all packagefile.yaml manifests under the incoming/ prefix.

    Example returned object key:

        incoming/<job-id>/packagefile.yaml
    """

    result = subprocess.run(
        [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            S3_BUCKET,
            "--prefix",
            INCOMING_PREFIX,
            "--query",
            f"Contents[?ends_with(Key, `{MANIFEST_NAME}`)].Key",
            "--output",
            "text",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    output = result.stdout.strip()

    if not output or output == "None":
        return []

    return output.split()


def extract_job_id(manifest_key: str) -> str:
    """
    Extract the UUID job ID from an incoming manifest key.

    Example:

        incoming/6f57c42b-953c-4db5-8564-c037c4ddc973/packagefile.yaml

    becomes:

        6f57c42b-953c-4db5-8564-c037c4ddc973
    """

    parts = manifest_key.split("/")

    return parts[-2]


def create_scheduling_job(
    job_id: str,
    manifest_key: str,
) -> None:
    """
    Create a scheduling object for the detected incoming job.

    Example:

        scheduling/<job-id>.yaml
    """

    scheduling_key = f"{SCHEDULING_PREFIX}{job_id}.yaml"

    timestamp = current_timestamp()

    content = (
        "job:\n"
        f"  id: {job_id}\n"
        "  status: scheduled\n"
        f"  source_manifest: {manifest_key}\n"
        f'  scheduled_at: "{timestamp}"\n'
    )

    subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            "-",
            f"s3://{S3_BUCKET}/{scheduling_key}",
        ],
        input=content,
        text=True,
        check=True,
    )

    print(
        f"[{current_timestamp()}] "
        f"Scheduling job created: "
        f"s3://{S3_BUCKET}/{scheduling_key}"
    )


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Scan S3 once for incoming submissions and then exit.

    GitHub Actions provides the recurring 5-minute schedule.
    """

    scan_start_time = current_timestamp()

    print()
    print("=" * 70)
    print("test-env2 S3 Scanner")
    print("=" * 70)
    print(f"Scan started     : {scan_start_time}")
    print(f"S3 bucket        : s3://{S3_BUCKET}")
    print(f"Scanning prefix  : {INCOMING_PREFIX}")
    print(f"Manifest pattern : */{MANIFEST_NAME}")
    print()

    # -----------------------------------------------------------------------
    # Step 1: Scan S3 for incoming manifests.
    # -----------------------------------------------------------------------

    print(
        f"[{current_timestamp()}] "
        "Starting scan for incoming jobs..."
    )

    manifests = find_incoming_manifests()

    scan_complete_time = current_timestamp()

    # -----------------------------------------------------------------------
    # Step 2: Handle case where no jobs were found.
    # -----------------------------------------------------------------------

    if not manifests:
        print()
        print(
            f"[{scan_complete_time}] "
            "Scan completed: no incoming jobs found."
        )

        print()
        print("-" * 70)
        print(
            "No work to process. Scanner is exiting normally."
        )
        print(
            "GitHub Actions will start the next scan "
            "on the next scheduled interval."
        )
        print("-" * 70)

        return

    # -----------------------------------------------------------------------
    # Step 3: Process discovered jobs.
    # -----------------------------------------------------------------------

    print()
    print(
        f"[{scan_complete_time}] "
        f"Scan completed: found {len(manifests)} incoming job(s)."
    )

    print()

    for manifest_key in manifests:

        job_id = extract_job_id(manifest_key)

        print("-" * 70)
        print(f"Job ID   : {job_id}")
        print(f"Manifest : {manifest_key}")
        print(
            f"Detected : {current_timestamp()}"
        )

        create_scheduling_job(
            job_id=job_id,
            manifest_key=manifest_key,
        )

    # -----------------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------------

    print()
    print("=" * 70)
    print("Scanner completed successfully.")
    print("=" * 70)
    print(f"Scan started     : {scan_start_time}")
    print(f"Scan completed   : {current_timestamp()}")
    print(f"Jobs discovered  : {len(manifests)}")
    print()

    print(
        "Scanner is exiting normally. "
        "GitHub Actions will start the next scan "
        "on the next scheduled interval."
    )


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()