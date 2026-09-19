# Storage durability evidence — P0 OPEN

Updated **2026-09-19 08:35 UTC**. Branch `codex/storage-durability`; changes are local and uncommitted. Local baseline HEAD is `d285886d4347e11578a5667ff4870f7c035b95fe`. Production is verified at that baseline commit; the storage implementation has **not** been committed or deployed. Staging deployed commit: **NOT RUN**. No paid resources, production deployment, restart, disk attachment or live migration was performed.

PASS means the stated scope was observed. NOT RUN is not a pass. Local fake-S3 and mount-fixture tests cannot demonstrate real AWS/Render durability. No athlete identities or credential values are included here.

## Local evidence

| Check | Status | Time (UTC, 2026-09-19) | Evidence / limit |
| --- | --- | --- | --- |
| Original reported suite | PASS | 07:34–07:36 | Re-ran all original 28 tests; all passed |
| Original engine scoring comparison | PASS | 07:41:45 | Exact pandas table equality and rival dictionaries against baseline `HEAD:update_engine.py`; 211 runners, 22 walkers |
| Repository backup/restore rehearsal | PASS | 07:41:45 | 31 managed files restored into an empty temporary directory, source/destination SHA-256 and mtimes equal, restored standings equal; archive 41,482 bytes. **Repository data only**, not live uploads |
| Expanded suite | PASS | 07:55 | 37 tests passed in 3.461 seconds; includes all original tests plus scheduler/monitoring/concurrent snapshot/worker checks |
| Final staging-probe helper change | PASS | 07:57 | Re-ran eight operations tests after deployed-commit validation adjustment |
| Two actual local Gunicorn serving workers | PASS | 07:55 | Synthetic HTTP responses from both existing worker PIDs changed 20 → 10 points, then rollback 10 → 20; fresh master/workers read 20 after a **local process restart** |
| Scheduler singleton | PASS | 07:55 | Second process cannot acquire `.backup-scheduler.lock`; can acquire after first releases it |
| Backup consistency during import | PASS | 07:55 | Import waits for snapshot shared lock; archive contains complete old result, subsequent target complete corrected result |
| Invalid/interrupted imports and rollback | PASS | 07:55 | Prior bytes/standings preserved on validation or pre-replace failure; recoverable journal/versions on post-replace interruption; journaled correction rollback tested |
| Shared maintenance pause | PASS | 07:55 | Publication rejects `.imports-paused` under the shared storage boundary |
| Backup integrity and retention | PASS | 07:55 | Fake S3 read-back, corruption rejection, restore, and retention-after-verification tests; **no real S3 request** |
| Monitoring decisions and secret-safe output | PASS | 07:55 | Missing/failed/stale/future-timestamp statuses unhealthy; healthy status emits 1; SDK failure output excludes sentinel secret. **No real alarm/email delivery** |
| Compilation / whitespace | PASS | 07:55 | Python compilation and `git diff --check` |
| Proposed YAML syntax | PASS | 07:53 | Ruby Psych parsed both Render proposals and CloudFormation proposal; **provider schema validation and deployment not run** |
| Official pricing verification | PASS | 07:53 | Render official pricing/plan documentation; AWS S3/CloudWatch/transfer regional public price lists. Extracts and source publication dates in `STORAGE_PRICING_EVIDENCE.json` |

Reproduce suite: `PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m unittest discover -s tests -v`. The real serving-worker test requires permission to create a local Unix socket; the initial sandbox run was denied and the authorized rerun passed. Test data are synthetic and temporary. The existing Flask-Limiter in-memory-backend warning remains outside this storage work.

## Actual staging infrastructure evidence

No staging resources have been approved or provisioned. Follow `STORAGE_STAGING.md`, `ops/render.staging.yaml.proposed`, and `ops/aws-storage.yaml.proposed`.

| Check | Status | Verified time / deployed commit | Missing evidence |
| --- | --- | --- | --- |
| Staging tier, disk ID/mount, one supervisor, two workers | NOT RUN | — / unknown | Resource approval, AWS account/region, Render access |
| Scheduled hourly backup reads same mounted disk as app | NOT RUN | — / unknown | Mount/device evidence and an actual scheduled S3 manifest containing the UI import |
| UI-imported synthetic results survive Render restart | NOT RUN | — / unknown | Actual restart and before/after checkpoint |
| Results survive Render redeploy | NOT RUN | — / unknown | Actual redeploy ID/commit and identical checkpoint |
| Independent S3 restore into empty location | NOT RUN | — / unknown | Real S3 object/read-back and independent machine restoration |
| Restored rules/mappings/checksums/standings match | NOT RUN | — / unknown | Real restore evidence |
| Invalid/interrupted import preserves last good staging data | NOT RUN | — / unknown | Run disposable fault tests on staging |
| Both actual serving workers see corrections and rollback | NOT RUN | — / unknown | Two staging worker PID/HTTP observations and rollback |
| Backup failure reaches operator | NOT RUN | — / unknown | Confirmed SNS subscription, failure alarm and received email |
| Stale backup and stopped-service alerts reach operator | NOT RUN | — / unknown | Independent CloudWatch missing-data evaluation, recorded latency and operator receipt |
| Resource capacity and rollback time | NOT RUN | — / unknown | Staging peak memory, disk capacity and timed restore; local archive size is not a live sizing input |

## Production/access evidence

| Check | Status | Time (UTC, 2026-09-19) | Observation / blocker |
| --- | --- | --- | --- |
| Authenticated Render dashboard | PASS | 08:15–08:34 | User signed in through the dashboard; inspection was read-only and settings edit mode was cancelled without saving |
| Service identity/source | PASS | 08:15 | `iac-league-web`; service `srv-d6je0rf5r7bs73f07cp0`; Production environment; Oregon (US West); GitHub `LetsDropCode/iac-league-web`, branch `main`, empty root directory |
| Deployed revision | PASS | 08:15 | Live deploy `dep-daajqa0ae00c73bfrk9g`; commit `d285886d4347e11578a5667ff4870f7c035b95fe`; latest successful trigger was Auto-Deploy |
| Compute/tier | PASS | 08:18 | Free, 0.1 CPU, 512 MB RAM, one instance; dashboard states Free has no shell/SSH, scaling, one-off jobs, or persistent disks |
| Commands and deploy policy | PASS | 08:15–08:34 | Build `pip install -r requirements.txt`; start `gunicorn app:app`; no pre-deploy command; auto-deploy verified **On Commit**; no health-check path; no PR previews |
| Runtime/workers | PASS | 08:25 | Render logs show Python 3.14 environment, Gunicorn 26.2.0, sync worker, one master and exactly one booted worker per observed cold start. Current command has no worker override; Gunicorn default is one |
| Environment variable names | PASS | 08:20 | Only `ADMIN_PASSWORD` and `SECRET_KEY`; values remained masked and were not copied or printed. No linked environment groups or secret files |
| Disk/mount | PASS | 08:19 | No disk. Disk page is an upgrade gate and explicitly says disks are unsupported on Free. No live mount path exists to inspect |
| Shell/SSH/live filesystem access | FAIL | 08:21 | Shell page is an upgrade gate; Free does not support shell/SSH. Upgrading would restart/redeploy the service before current ephemeral files were backed up |
| Cold-start behavior | PASS (risk evidence) | 08:25 | Logs show repeated master/worker termination and fresh starts on 2026-09-19, consistent with Free spin-down. This demonstrates exposure to ephemeral reset; it does not inventory live files |
| Other hosting access | NOT RUN | 07:54 | No Render connector/CLI, AWS CLI/config directory or relevant credential/config environment variable names available. No secret values printed |
| Resource/cutover cost approval | NOT RUN | — | Explicitly not granted; conditional single approval scope in `STORAGE_COSTS.md` |
| CURRENT LIVE inventory | NOT RUN | — | No safe access to the running instance. Do not substitute repository files |
| Independent current-live backup/read-back/restore | NOT RUN | — | Safe live extraction, approved S3 account/resources and independent recovery access required |
| Coordinated import freeze/final backup/checksum migration | NOT RUN | — | Must pass live backup and staging gates before any disruptive production change |
| Production restart persistence | NOT RUN | — / commit unknown | Requires approved controlled cutover and actual before/after evidence |
| Production redeploy persistence | NOT RUN | — / commit unknown | Requires approved redeploy and actual before/after evidence |
| Independent production restoration and standings comparison | NOT RUN | — / commit unknown | Requires actual live S3 backup restored independently |
| Imports reopened / P0 closed | NOT RUN | — | **P0 OPEN** until production persistence, independent restoration and alerts are demonstrated |

**Exact current blocker:** authenticated inspection confirms the live service is Free and has no shell/SSH or disk. Render offers those capabilities only after upgrading, and applying the upgrade would restart/redeploy the service before current ephemeral files could be inventoried and independently backed up. Do not upgrade, change environment/start commands, restart/redeploy, or attach a disk to obtain access. Arrange a non-restarting extraction with Render Support, or obtain another verified current-live-data source from the application owner. Repository files cannot substitute for live uploads.

## Preparation completed in this continuation

- Added a cross-process singleton scheduler lock; proposed two explicit serving workers in the same disk-owning service.
- Added a separate monitoring thread and prepared independent CloudWatch alarm/SNS configuration. Missing metrics alarm independently of Render. Credentials remain external to Git.
- Added a shared import-pause command, synthetic staging fixture/probe, read-only value-redacted runtime inspector, and concrete staging/rollback/failure-drill steps.
- Verified current rate tables and separated production increments from temporary staging costs in `STORAGE_COSTS.md`.
- Prepared a single conditional approval scope. No infrastructure evidence above is inferred from configuration files.
