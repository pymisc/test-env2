# test-env2 — Scheduler Environment

`test-env2` simulates the **scheduler / consumer side** of a split-environment build and qualification workflow.

The repository periodically scans a shared Amazon S3 bucket for new artifact submissions created by `test-env1`. When a completed submission is detected, it creates a scheduling record for that job.

## Architecture

```text
┌─────────────────────────────┐
│          AWS S3             │
│      split-env-data         │
│                             │
│ incoming/<UUID>/            │
│ ├── packagefile.bin         │
│ └── packagefile.yaml        │
└──────────────┬──────────────┘
               │
               │ scan incoming/
               ▼
┌─────────────────────────────┐
│        GitHub Actions       │
│    Scheduler CI Pipeline    │
│                             │
│    scheduled periodically   │
│       / manual run          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│         scanner.py          │
│                             │
│  1. Scan incoming/          │
│  2. Find manifests          │
│  3. Extract UUID            │
│  4. Create scheduling job   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│          AWS S3             │
│                             │
│ scheduling/                 │
│ └── <UUID>.yaml             │
└─────────────────────────────┘
```

## Workflow

`test-env1` publishes artifact submissions using the following structure:

```text
s3://split-env-data/

incoming/
└── <UUID>/
    ├── packagefile.bin
    └── packagefile.yaml
```

The binary artifact is uploaded first and `packagefile.yaml` is uploaded last.

The presence of:

```text
incoming/<UUID>/packagefile.yaml
```

therefore acts as the **submission-ready signal**.

`scanner.py` performs the following operations:

1. Scans the S3 `incoming/` prefix.
2. Searches for `packagefile.yaml` manifests.
3. Extracts the UUID from each discovered submission.
4. Creates a scheduling record for each discovered job.
5. Exits after completing one scan.

GitHub Actions is responsible for periodically starting the next scan.

## Scheduling Record

When an incoming job is discovered, the scanner creates:

```text
s3://split-env-data/scheduling/<UUID>.yaml
```

Example:

```yaml
job:
  id: 6f57c42b-953c-4db5-8564-c037c4ddc973
  status: scheduled
  source_manifest: incoming/6f57c42b-953c-4db5-8564-c037c4ddc973/packagefile.yaml
  scheduled_at: "2026-08-14T17:30:00+00:00"
```

The UUID provides a common **correlation ID** between the producer artifact and its scheduling state.

## CI Pipeline

The GitHub Actions workflow is defined in:

```text
.github/workflows/ci.yaml
```

The **Scheduler CI Pipeline** runs on:

- Scheduled execution using GitHub Actions cron
- Pushes to `main`
- Manual `workflow_dispatch`

The configured schedule is:

```yaml
schedule:
  - cron: "2/5 * * * *"
```

The offset avoids scheduling directly on the top-of-hour boundary.

The pipeline flow is:

```text
GitHub Actions
      │
      ▼
Scheduled / Manual / Push
      │
      ▼
Checkout Repository
      │
      ▼
Setup Python
      │
      ▼
Authenticate to AWS
      │
      │ OIDC + STS
      ▼
Assume IAM Role
test-env2-producer
      │
      ▼
Run scanner.py
      │
      ▼
Scan S3 incoming/
      │
      ├── No jobs ──► Exit normally
      │
      └── Jobs found
              │
              ▼
        Create scheduling
            records
              │
              ▼
             Exit
```

## AWS Authentication

GitHub Actions authenticates to AWS using:

```text
GitHub OIDC
     │
     ▼
AWS STS
AssumeRoleWithWebIdentity
     │
     ▼
test-env2-producer
     │
     ▼
Amazon S3
```

No permanent AWS access keys are stored in the repository.

## Scanner Execution Model

`scanner.py` does **not** run continuously.

Each invocation performs one scan:

```text
Start
  │
  ▼
Scan incoming/
  │
  ├── Nothing found ──► Log result ──► Exit
  │
  └── Jobs found ─────► Schedule jobs ──► Exit
```

GitHub Actions provides the recurring execution schedule.

This keeps the scanner itself stateless and avoids keeping a CI runner alive while waiting between scans.

## Current S3 State Model

```text
split-env-data/
│
├── incoming/
│   └── <UUID>/
│       ├── packagefile.bin
│       └── packagefile.yaml
│
└── scheduling/
    └── <UUID>.yaml
```

Future workflow stages can extend this model with additional states such as:

```text
in-progress/
results/
completed/
failed/
```

The same UUID can be used throughout the workflow to correlate the artifact, scheduling state, worker execution, and final qualification result.

## Producer Handoff

The producer side of this workflow is implemented separately in `test-env1`.

The overall handoff is:

```text
test-env1
Producer
   │
   │ publish
   ▼
incoming/<UUID>/
   │
   │ detect
   ▼
test-env2
Scheduler
   │
   ▼
scheduling/<UUID>.yaml
```

This models communication between two isolated environments using a shared object store as the exchange mechanism.