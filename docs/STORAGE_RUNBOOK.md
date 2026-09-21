# Storage durability and recovery

**P0 remains open until the live restart/redeploy persistence test and independent restore drill below are demonstrated.** This branch is implementation and a proposed cutover, not evidence that live data is durable.

## Accepted migration baseline

On 21 September 2026, the owner accepted `outputs/recovery/local-recovery-candidate.zip` (SHA-256 `95b2d0836e5158ee999c9ed8eedda5843ad5c27f0aa51ffd959baaa23f610221`) as the authoritative production migration baseline. See `outputs/recovery/BASELINE-ACCEPTANCE.md` for scope and limitations. This resolves the owner-acceptance decision only; it does not claim byte-for-byte equivalence with the inaccessible live filesystem and does not waive staging, independent-backup, restore, persistence, monitoring, cost, access, or maintenance-window gates.

## Verified facts and remaining hosting unknowns (2026-09-19)

- Repository baseline: `main`; implementation branch: `codex/storage-durability`. No AGENTS.md was found in the repository or ancestor directories. The baseline has a Gunicorn Procfile, relative `results/`, and root-level `points_rules.csv`, `points_rules_walk.csv`, `category_map.csv`; no Render Blueprint/disk configuration.
- Authenticated dashboard inspection verified production service `srv-d6je0rf5r7bs73f07cp0`, Oregon, Free (0.1 CPU/512 MB), one instance, no disk, no shell/SSH, branch `main`, deployed commit `d285886d4347e11578a5667ff4870f7c035b95fe`, build `pip install -r requirements.txt`, start `gunicorn app:app`, auto-deploy **On Commit**, and only environment variable names `ADMIN_PASSWORD` and `SECRET_KEY`. Values remained masked. Logs show Python 3.14, Gunicorn 26.2.0 and one sync worker per cold start. Backup destination/history and current live file inventory remain unverified.
- No production restart, deploy, mount, migration, backup upload or paid resource creation was performed.
- [Render disk documentation](https://render.com/docs/disks): persistent disks require a paid service; only paths under the disk mount persist. Adding a disk triggers deployment. Disks are unavailable to builds, pre-deploy commands, one-off jobs and other services (including cron services). Single service instance only. Built-in snapshots are supplemental, not this application's independent backup.
- [Render Blueprint reference](https://render.com/docs/blueprint-spec) documents the proposed fields. `render.yaml.proposed` deliberately is not the auto-discovered `render.yaml`. Do not connect it to a new Blueprint blindly: first reconcile it with the existing service and repository/branch/runtime settings. The proposed Starter tier and 1 GB disk need approval and capacity review; they are not verified live settings.

## Storage contract

All runtime mutable inputs live under absolute, canonical `LEAGUE_DATA_DIR`:

```
results/                 uploaded CSV and XLSX (original bytes)
points_rules.csv         mutable running rules
points_rules_walk.csv    mutable walking rules
category_map.csv         mutable mappings
versions/<sha256>        immutable prior and proposed publication bytes
publications/*.json      prepared/committed publication journal
migrations/*.json        reviewed inventories and verified migration reports
.storage.json            operator-initialized volume identity
exports/                 regenerated league_tables.xlsx (not backed up)
.storage.lock            advisory interprocess lock (not backed up)
.backup-status.json      latest backup status (not backed up)
```

Local development defaults to the absolute repository directory (regardless of working directory); existing local results and rules continue to work. An explicit `LEAGUE_DATA_DIR` overrides that default. No startup code copies seed data. Initialize a separate development directory explicitly using migration/restore or copy selected fixtures while offline. Keep development and production separate.

Production is detected by `RENDER` or `LEAGUE_ENV=production`. Startup requires explicit data dir, a dedicated Linux mount at `LEAGUE_DISK_MOUNT`, a read/write ext4/xfs/btrfs filesystem in `/proc/self/mountinfo`, a matching `LEAGUE_VOLUME_ID` in `.storage.json`, results directory, valid rule/mapping schemas, and write access. A writable directory, environment assertion, or marker alone is insufficient. Unsupported filesystem types fail closed; inspect the actual mount rather than relaxing this check. This mount verification does not replace control-plane verification or a restart test. Non-Render production must set `LEAGUE_ENV=production`.

Imports parse and validate required columns/nonempty data before publication. Existing nonfinishers and scoring rules retain their semantics. Cross-process `flock` serializes publication, migration, restore and backup snapshots; scoring takes a shared lock. Use these tools for all edits; manual writes bypass the safety contract. Imports with identical bytes are idempotent; different bytes for an existing filename are rejected. Operator replacements require the current SHA-256. Each publication archives old/new bytes and a prepared record before fsynced same-filesystem temporary-file replacement. The commit record is then updated. A crash after replacement may leave `prepared` despite successful publication; see recovery below. Temp files never count as results. No worker-specific score cache remains.

Rules and mappings are backed up byte-for-byte; scoring calculations are unchanged. Export with `python update_league.py`; output is under `LEAGUE_DATA_DIR/exports/league_tables.xlsx`. `convert_agn.py --expected-sha256 CURRENT_HASH` uses the publication mechanism for rules. Its existing spreadsheet conversion policy is unchanged.

## Independent backup setup (approval/access required)

Use a private **AWS S3 bucket**, independent of Render and its disk, preferably in a separate recovery account. Do not use a second directory on `/var/data`. The tool intentionally accepts no filesystem backup destination. Approve any S3/Render costs first. Enable public-access blocking, encryption and bucket versioning; retain recovery credentials outside Render. Give the runtime principal `s3:ListBucket` scoped to the dedicated prefix, `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on that prefix, and `cloudwatch:PutMetricData` constrained to `IACLeague/Storage`. It must not be able to change/delete alarms, bucket policy or noncurrent object versions. The proposed CloudFormation template creates a policy to attach to an approved runtime principal, not credentials. Retention deletes old keys; if using versioning, configure a reviewed lifecycle policy for noncurrent versions (e.g. 30 days) so old versions remain recoverable without unlimited cost. Object Lock can provide stronger protection with an independently administered retention policy; coordinate application deletion permissions accordingly.

Set `LEAGUE_MONITOR_SERVICE=iac-league-production` matching the independently provisioned alarm. Set `LEAGUE_BACKUP_BUCKET`, dedicated `LEAGUE_BACKUP_PREFIX=iac-league/`, `AWS_DEFAULT_REGION`, and standard AWS credentials in Render secrets/environment and the operator's secure credential store. Session credentials also require `AWS_SESSION_TOKEN`. Never put secrets in Git, shell arguments, plans, tickets or this document. `.env*` is ignored, but do not store production secrets in the checkout. The implementation uses the standard boto3 credential chain and AWS HTTPS endpoints. No S3-compatible endpoint override is supplied.

The runtime start command `python backup_runner.py` takes a nonblocking exclusive `.backup-scheduler.lock` for the supervisor lifetime. A second scheduler exits without running. It verifies an initial independent backup and checks CloudWatch metric access **before** starting Gunicorn (explicit `WEB_CONCURRENCY`, proposed value 2), then backs up hourly from the disk-owning instance. Scheduler and serving processes share the same `LEAGUE_DATA_DIR`; no separate cron service is provisioned. A shared storage lock makes each snapshot consistent with imports. Only the snapshot phase blocks publications; remote upload/read-back happens after releasing that shared lock. Default production retention is 168 verified snapshots (roughly seven days at hourly cadence); CLI default is 30. Each archive contains a per-file SHA-256/size/mtime manifest and all managed data, including versions and metadata. Uploads use unique keys and AES256 server-side encryption. The entire object is downloaded and verified before success and before pruning older managed keys. Failures exit CLI nonzero, log `BACKUP_FAILED`, and write `.backup-status.json` with `verified: false`; later successes replace that status. A failed periodic backup does not terminate the web server.

**Required operational monitoring:** provision and test `ops/aws-storage.yaml.proposed` after approval. The supervisor emits one credential-free `BackupHealthy` CloudWatch metric every minute from a thread independent of backup I/O. It reports unhealthy after a failed backup or when verified backup age reaches two hours. The independent CloudWatch alarm also treats missing metrics as breaching, so stopping the entire Render service does not silence monitoring. Confirm the approved SNS email subscription and actual failure/missing/recovery delivery in staging; configuration alone is not evidence. See `STORAGE_STAGING.md` for latency targets and tests. Logs and `.backup-status.json` provide additional diagnostics. None of these AWS resources are provisioned yet. Target RPO is one hour while backups are healthy; RTO must be measured by the drill. Local versions are recovery aids, not independent backups. Monitor disk utilization; versions are intentionally not automatically purged. Increase disk size only with approval.

## Safe cutover: backup before any redeploy or new mount

Before this sequence, review `STORAGE_COSTS.md` and obtain its single conditional resource/cutover approval. Run the isolated acceptance sequence in `STORAGE_STAGING.md`; all infrastructure checks must pass before production cutover. No current-live-data access, pricing approval or staging pass is inferred from local tests.

1. Dashboard inspection is complete and recorded in `STORAGE_VERIFICATION.md`. The live Free tier has no shell/SSH or disk, and the Render dashboard support response says there is no supported way to access that running filesystem without restart/replacement. **Stop here for production.** Obtain a complete, provenance-confirmed set of owner-retained source files, or prove that an export already present in the deployed application returns every managed file byte-for-byte. Do not deploy a new export endpoint: that deployment could erase the ephemeral files it is intended to recover. Only after a verified recovery source exists, use `ops/inspect_runtime.py` where safe access is available to capture UTC time, cwd, mount paths/filesystems, process roles/PIDs and environment **names only**. It never returns raw process arguments or environment values.
2. After approval, disable automatic deployments only if the dashboard confirms that edit will not restart the running service. Arrange an operator-enforced import freeze without restarting the service. Coordinate all admins to stop uploads/rule changes and verify no imports are in flight. The old app does not honor the new lock, so advisory locks alone cannot freeze it. If you cannot guarantee this, do not cut over. Keep imports frozen until the final snapshot has been independently restored and the new service verified.
3. Transfer `storage.py` and `storage_ops.py` into an isolated tools directory in the **currently running** instance using authenticated SSH/SCP (or Render's documented Shell/wormhole workflow). Do not deploy the branch yet. Provide Python dependencies in an isolated environment if needed; do not replace the running application's environment. Configure authorized independent backup credentials in that shell. Set `LEGACY_ROOT` to the verified absolute directory containing live `results/` and the three CSVs (typically `/opt/render/project/src`, but verify).
4. Inventory, back up and independently restore **before adding a disk**:

   ```sh
   python storage_ops.py inventory --source "$LEGACY_ROOT" > /tmp/live-inventory.json
   python storage_ops.py backup --source "$LEGACY_ROOT" --retain 168 > /tmp/backup-receipt.json
   ```

   Check exit status, `verified: true`, object key and SHA-256. Transfer the inventory/receipt off the instance securely. On another computer with recovery credentials and the same tooling:

   ```sh
   python storage_ops.py restore --key 'KEY_FROM_RECEIPT' --destination /absolute/new/restore-drill
   python storage_ops.py inventory --source /absolute/new/restore-drill > /tmp/restored-inventory.json
   ```

   Compare every file's SHA-256, size and mtime to the live inventory. Check counts, representative uploaded files, rules and category mappings. Run `LEAGUE_DATA_DIR=/absolute/new/restore-drill python update_league.py` and compare rankings/totals with the live baseline. Capture evidence and elapsed restoration time. Do not mistake repository results for a live backup. Preserve extra legacy files found outside the managed paths separately if the hosting inventory reveals them.
5. Produce a reviewable migration plan from the independently restored live snapshot to an empty staging directory:

   ```sh
   python storage_ops.py migrate --source /absolute/new/restore-drill \
     --destination /absolute/new/migration-rehearsal --plan /tmp/rehearsal-plan.json
   python storage_ops.py migrate --source /absolute/new/restore-drill \
     --destination /absolute/new/migration-rehearsal --plan /tmp/rehearsal-plan.json \
     --apply --backup-key 'KEY_FROM_RECEIPT'
   ```

   Review complete source/destination inventory and `conflicts` before apply. Conflicts stop all copying. The source is never deleted or altered (other than creating its lock file). Destination-only files remain preserved. An interruption may leave a subset copied; generate a **new** plan and review it to resume. Never reuse a stale plan or remove a conflict simply to make migration pass.
6. Only after the independent backup and drill, review/approve the cutover and costs. Attach the proposed new disk at **`/var/data`**, never over the old `results/` or source directory. Adding a disk deploys the service and may destroy the old ephemeral files, which is why the previous steps are mandatory. Use a planned maintenance window; keep imports disabled. Preserve old start command, env and deployed commit in the change record.
7. Deploy this branch with the proposed production variables and runtime command. An empty disk will deliberately fail startup. From the disk-owning service Shell/SSH, restore the independent backup into `/var/data/staging-live` (not a build/predeploy/one-off job). Generate a fresh plan with source `/var/data/staging-live` and destination `/var/data/league`; inspect it and apply with the verified backup key. If Shell is unavailable while the app fails startup, configure a temporary maintenance-only HTTP service as described below, then populate the disk and restore the production start command. Never weaken production checks or start the old import UI during maintenance.
8. Pause imports in the new destination with `python storage_ops.py pause-imports --source /var/data/league`. This is a shared disk marker checked under the publication lock by every worker; it does not protect the old app in step 2. For a first migration without identity, choose a UUID and initialize explicitly:

   ```sh
   python storage_ops.py initialize --destination /var/data/league --volume-id 'APPROVED_UUID'
   ```

   Set `LEAGUE_VOLUME_ID` to that same UUID in Render. Existing backup identities must be preserved, not silently replaced. `initialize` refuses a different existing identity. Verify the mount is read/write at `/var/data`, inspect plan/report, then start `python backup_runner.py`. Confirm startup backup read-back and the app's results, histories, latest race, points and export. Use the existing service's repository/branch settings; do not accidentally create a second service from the proposal.

If maintenance HTTP is required in step 7, temporarily use this start command, which recreates a separate maintenance directory at every boot:

```sh
mkdir -p /tmp/league-maintenance && printf 'League maintenance' > /tmp/league-maintenance/index.html && python -m http.server "$PORT" --bind 0.0.0.0 --directory /tmp/league-maintenance
```

Preserve the existing Python runtime version until verified compatible (the code requires Python 3.9+). Do not serve the repository, data directory or credentials. This change is allowed only in the approved cutover after the independent backup; it is not performed by this task.

## Persistence acceptance gate — required before P0 closure

While still in the approved maintenance/test window:

1. Save a full destination inventory and independently verified S3 backup receipt. Record disk ID, mount info, volume ID, commit and timestamps.
2. Keep production imports paused. Use the latest actual live upload captured in the final backup as the production persistence subject; record its hash and the rules/mapping hashes. The staging sequence separately exercises an import through the real UI. If a newly approved live import is required for acceptance, coordinate a brief deliberate unpause/re-pause and capture a new independent backup/checkpoint before the restart. Do not inject a fake athlete into live league scoring.
3. Restart the disk-backed service, then redeploy the same commit separately. After **each**, compare inventory hashes and verify latest result, athlete history, rules and export still read from `/var/data/league`. Record any expected publication/backup status differences separately.
4. Restore the latest remote backup into a fresh directory on an independent machine. Verify all checksums and compare league totals/rankings and histories. Record recovery duration and backup age.
5. Only then run `python storage_ops.py resume-imports --source /var/data/league`, lift the coordinated admin freeze and sign off P0. Sign-off also requires a confirmed external alert recipient and tested failure/missing-backup notification. Re-enable auto-deploy only through the normal change process. Keep backup alerts and periodic restore drills active.

## Rollback and recovery

- **Before cutover:** no source content is changed by the tooling. Abandon the staged destination and continue the existing service after lifting the freeze; retain the independent backup.
- **After cutover:** keep the disk and data intact. Roll back application code only to a revision that honors `LEAGUE_DATA_DIR`; the old `main` does not. Never simply redeploy old code pointed at repository seeds. To recover with old code, an operator must explicitly adapt its paths to the restored data in a reviewed maintenance plan. Prefer forward-fixing this branch while the app remains in maintenance.
- **Disk loss/corruption:** freeze imports, retain the damaged directory for investigation, and restore a chosen verified S3 key to a **new empty directory** on an approved replacement disk. The restore command checks all archive members before writing and rejects conflicting destination contents. Initialize only if identity is absent; preserve a backed-up identity and set the matching environment value. Verify inventories and scoring before switching `LEAGUE_DATA_DIR`. Obtain approval for additional disks/costs. Restoration never deletes unrelated files.
- **Interrupted publication:** under maintenance, inspect `publications/*.json`. Compare the target SHA-256 with `before` and `after`. A `prepared` entry with the `after` hash means replacement succeeded before commit metadata; a `before` hash (or absent target for a new import) means it did not. A different hash may belong to a later committed publication; review the chronological journal before acting. Both candidate byte versions are retained by hash. Do not blindly replay every prepared record.
- **Reviewed replacement/rollback:** use a version or corrected file with `publish`, passing the **current** target hash as the expected value. This makes rollback a new journaled publication, preserving both versions:

  ```sh
  python storage_ops.py publish --source /var/data/league \
    --name results/EXACT_EXISTING_FILENAME.csv \
    --file /var/data/league/versions/PRIOR_SHA256 \
    --expected-sha256 CURRENT_TARGET_SHA256
  ```

  Rules and mapping rollback use `--name points_rules.csv`, `points_rules_walk.csv`, or `category_map.csv`. Invalid/stale expectations fail without overwrite. A new independent backup should follow an operator correction.
- **Backup failure:** investigate credentials, connectivity, S3 access, capacity and the first error. Run an explicit backup, require successful read-back, check the independent monitor, then repeat a restore drill. Do not delete local versions or prune remote backups to hide failures.

## Local verification

```
python -m pip install -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Tests use temporary directories and a fake independent object-store client; no cloud charges or live changes. They exercise paths, fail-closed production checks, atomic-write interruption before and after replacement, multi-process conflicts, checksum migration and retries, restore conflicts/corruption, and remote read-back/retention. These tests do not prove the actual Render disk or AWS account configuration. Keep operational evidence separately; never claim a local simulation is a live persistence demonstration.
