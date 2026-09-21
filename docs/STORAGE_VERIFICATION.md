# Storage durability evidence — P0 OPEN

Updated **2026-09-21 19:13 UTC**. Branch `codex/storage-durability`; the combined implementation and recovery-evidence commit `9ecedef` is present on `origin/codex/storage-durability`. Production remains at baseline commit `d285886d4347e11578a5667ff4870f7c035b95fe`; the storage implementation has **not** been deployed to production. Render staging deployed commit: **NOT RUN**. Isolated AWS staging resources were provisioned; no Render resource, production deployment, restart, disk attachment or live migration was performed.

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

The AWS stack `iac-league-staging-storage` reached `CREATE_COMPLETE` in `eu-north-1` at 19:13:08 UTC on 21 September 2026. Its reviewed change set contained exactly six additions: private encrypted/versioned S3 storage, TLS-only bucket policy, SNS topic/policy, CloudWatch missing/failure alarm, and restricted runtime IAM policy. All six resources reached `CREATE_COMPLETE`; expected bucket, alarm, and policy outputs exist. The SNS console subsequently showed the operator email subscription as `Confirmed`. No keys were generated and the runtime policy is not attached. Repository-safe evidence is in `outputs/staging/AWS-PROVISIONING.md`; physical identifiers and operator contact data are omitted.

Render staging has not been provisioned. Its proposal targets `codex/storage-durability`, starts in maintenance mode for explicit empty-disk seeding, uses one 1 GB `/var/data` disk and one in-service backup supervisor with two Gunicorn workers. The labelled synthetic fixture SHA-256 is `e8df6d47b2dc6b27c6ffef62188102324b7aae166b2f5a91bf7a21f5ef287c00`.

| Check | Status | Verified time / deployed commit | Missing evidence |
| --- | --- | --- | --- |
| Reviewed staging deployment inputs | PASS (AWS deployed; Render prepared) | 2026-09-21 19:13 UTC / AWS template SHA-256 `a45a0f53e8fba7183e09fd73cee09d3a5bbf05f7861d60ba60f7d97ad5b2ac37` | Staging runtime principal, Render billing permission and provider-side secrets |
| Staging tier, disk ID/mount, one supervisor, two workers | NOT RUN | — / unknown | Resource approval, AWS account/region, Render access |
| Scheduled hourly backup reads same mounted disk as app | NOT RUN | — / unknown | Mount/device evidence and an actual scheduled S3 manifest containing the UI import |
| UI-imported synthetic results survive Render restart | NOT RUN | — / unknown | Actual restart and before/after checkpoint |
| Results survive Render redeploy | NOT RUN | — / unknown | Actual redeploy ID/commit and identical checkpoint |
| Independent S3 restore into empty location | NOT RUN | — / unknown | Real S3 object/read-back and independent machine restoration |
| Restored rules/mappings/checksums/standings match | NOT RUN | — / unknown | Real restore evidence |
| Invalid/interrupted import preserves last good staging data | NOT RUN | — / unknown | Run disposable fault tests on staging |
| Both actual serving workers see corrections and rollback | NOT RUN | — / unknown | Two staging worker PID/HTTP observations and rollback |
| Backup failure reaches operator | NOT RUN (subscription confirmed) | 2026-09-21 / AWS staging stack | Failure state transition and received alarm email |
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
| Render dashboard support response | FAIL (no extraction path) | 18:14 | Screenshot supplied by the owner shows Render's dashboard support response: no supported filesystem access for a running Free service without restart/replacement; `render ssh` requires paid service; ephemeral writes are lost on restart, redeploy or spin-down. It recommends an in-application copy/archive before disruption. No case ID or human-escalation evidence is visible |
| Cold-start behavior | PASS (risk evidence) | 08:25 | Logs show repeated master/worker termination and fresh starts on 2026-09-19, consistent with Free spin-down. This demonstrates exposure to ephemeral reset; it does not inventory live files |
| Other hosting access | NOT RUN | 07:54 | No Render connector/CLI, AWS CLI/config directory or relevant credential/config environment variable names available. No secret values printed |
| Resource/cutover cost approval | PASS (conditional) | 2026-09-21 | Owner approved the scope and limits in `STORAGE_COSTS.md`; AWS staging is provisioned, Render and production gates remain |
| CURRENT LIVE inventory | NOT RUN | — | No safe access to the running instance. Do not substitute repository files |
| Independent current-live backup/read-back/restore | NOT RUN | — | Safe live extraction, approved S3 account/resources and independent recovery access required |
| Coordinated import freeze/final backup/checksum migration | NOT RUN | — | Must pass live backup and staging gates before any disruptive production change |
| Production restart persistence | NOT RUN | — / commit unknown | Requires approved controlled cutover and actual before/after evidence |
| Production redeploy persistence | NOT RUN | — / commit unknown | Requires approved redeploy and actual before/after evidence |
| Independent production restoration and standings comparison | NOT RUN | — / commit unknown | Requires actual live S3 backup restored independently |
| Imports reopened / P0 closed | NOT RUN | — | **P0 OPEN** until production persistence, independent restoration and alerts are demonstrated |

**Exact current gate:** the owner accepted the committed local recovery candidate as the authoritative production migration baseline on 21 September 2026, with the limitations recorded in `outputs/recovery/BASELINE-ACCEPTANCE.md`. AWS staging storage and monitoring are provisioned and the SNS subscription is confirmed, but the runtime principal and Render staging have not been created or tested. Do not upgrade, change environment/start commands, restart/redeploy, or attach a production disk until the isolated Render staging sequence and independent backup/restore evidence pass.

## Preparation completed in this continuation

- Added a cross-process singleton scheduler lock; proposed two explicit serving workers in the same disk-owning service.
- Added a separate monitoring thread and prepared independent CloudWatch alarm/SNS configuration. Missing metrics alarm independently of Render. Credentials remain external to Git.
- Added a shared import-pause command, synthetic staging fixture/probe, read-only value-redacted runtime inspector, and concrete staging/rollback/failure-drill steps.
- Verified current rate tables and separated production increments from temporary staging costs in `STORAGE_COSTS.md`.
- Prepared a single conditional approval scope. No infrastructure evidence above is inferred from configuration files.
