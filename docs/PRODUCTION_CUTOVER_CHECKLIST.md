# Production persistence cutover checklist

Prepared on **24 September 2026** and updated on **25 September 2026** after all isolated staging gates passed. This is a preparation record, not authorization to change production. The detailed procedure and safety rationale remain in `STORAGE_RUNBOOK.md`; if the two documents differ, stop and resolve the difference before acting.

## Current status

**NO-GO.** Do not restart, redeploy, upgrade, attach a disk to, change environment variables on, or otherwise modify production until every mandatory gate below is marked PASS and the owner explicitly starts the maintenance window.

Candidate prepared from branch `codex/storage-durability`:

- Application/dependency candidate commit: `42a6adfe2bd836930302759709dcdab7c70b1f0a`
- Remote candidate branch at dependency verification: `42a6adfe2bd836930302759709dcdab7c70b1f0a`
- Staging pinned-build deploy: `dep-dar151h42hec73cjuddg`
- Accepted recovery artifact: `outputs/recovery/local-recovery-candidate.zip`
- Accepted recovery SHA-256: `95b2d0836e5158ee999c9ed8eedda5843ad5c27f0aa51ffd959baaa23f610221`
- Production configuration proposal SHA-256: `d1bca3d18028acde337fe401ee2001b778ebf599700e8f9a85464f9e346e3cdb`
- Staging configuration proposal SHA-256: `93240855efaa2398c685f621e8b692fbe3bad9e622de44db03e49552e282418d`
- Dependency lock SHA-256: `d5dfdac6d9c735b6442601ba0d53b05fe1eef5c4307ecc15d35440de313e3846`
- AWS configuration proposal SHA-256: `1e57fca32f52655d7264842420693aa0d4d6c44dbd9b86ba56ff222f519816de`

Local verification at candidate preparation:

- [x] All 50 unit/integration tests passed, including two Gunicorn workers, correction, rollback, restart, backup, restore, monitoring and import locking.
- [x] Six operational Python files compiled from source.
- [x] `render.yaml.proposed`, `ops/render.staging.yaml.proposed` and `ops/aws-storage.yaml.proposed` parsed as YAML.
- [x] `git diff --check` passed.
- [x] Accepted recovery source completed a local migration, scoring, backup and exact restore rehearsal; see `PRODUCTION_CUTOVER_DRY_RUN.md`.
- [x] Final staging stale-backup-with-monitor-alive drill passed and operator confirmed receipt of ALARM and OK/recovery emails.
- [x] Staging rebuilt from `requirements.lock`; Python 3.14.3 reported no broken requirements and the runtime package set exactly matched the lockfile.

The Flask-Limiter test warning about its in-memory backend remains known and outside the storage cutover scope. It must not be misreported as a persistence-test failure or silently treated as production-grade distributed rate limiting.

## Mandatory go/no-go gates

The cutover is GO only when every item is checked and evidence is recorded in `STORAGE_VERIFICATION.md`.

- [x] Final staging stale-backup drill passed: backup age exceeded 7,200 seconds while the monitor continued emitting.
- [x] CloudWatch entered ALARM within the documented stale-backup target.
- [x] Operator received the ALARM email.
- [x] The staging lock was released, a verified backup completed, and CloudWatch returned to OK.
- [x] Operator received the OK/recovery email.
- [x] Staging runtime and alarm were returned to their expected healthy configuration; no temporary IAM deny policy remains.
- [ ] Owner reviewed the final staging evidence and explicitly approved production cutover.
- [ ] Maintenance start and maximum-duration window are recorded below.
- [ ] Import-freeze owner and cutover operator are present and reachable.
- [x] Accepted recovery archive exists in the production recovery bucket and independent operator read-back matched the accepted SHA-256.
- [x] Production AWS bucket, runtime policy, alarm, SNS subscription and independent recovery access are provisioned and verified without exposing secret values.
- [x] Production dependencies are reproducible from the tested staging package set in `requirements.lock`; staging deploy `dep-dar151h42hec73cjuddg` installed it and matched it exactly.
- [x] Exact release commit and configuration hashes were regenerated and reviewed after the pinned staging deployment.
- [x] No unreviewed application changes are included in the production release candidate.

Any unchecked item means NO-GO.

## Roles and window

Fill these fields before the owner starts the cutover. Do not place email addresses, credentials, secret values or recovery keys in this repository.

| Item | Required value |
| --- | --- |
| Owner / final go-no-go authority | `TBD` |
| Cutover operator | `TBD` |
| Import-freeze owner | `TBD` |
| Independent restore verifier | `TBD` |
| Alert recipient confirmed | `TBD — record yes/no only` |
| Maintenance start, UTC | `TBD` |
| Maximum maintenance duration | `TBD` |
| Abort-decision time, UTC | `TBD` |
| Operator communication channel | `TBD — name only, no contact details` |

## Frozen production configuration sheet

Review against the existing `iac-league-web` service before saving any dashboard change. Secret values must be entered from the approved secret store and must never be copied into evidence.

| Setting | Required value |
| --- | --- |
| Service / region | Existing `iac-league-web` / Oregon |
| Repository | `https://github.com/LetsDropCode/iac-league-web` |
| Release commit | `42a6adfe2bd836930302759709dcdab7c70b1f0a` |
| Build command | `python -m pip install -r requirements.lock` |
| Start command after data restore | `python backup_runner.py` |
| Plan / instances | Starter-equivalent / 1 |
| Disk | `league-data`, 1 GB, mounted at `/var/data` |
| Auto-deploy | Off during cutover |
| `LEAGUE_DEPLOYMENT_STAGE` | `production` |
| `LEAGUE_ENV` | `production` |
| `LEAGUE_DATA_DIR` | `/var/data/league` |
| `LEAGUE_DISK_MOUNT` | `/var/data` |
| `LEAGUE_VOLUME_ID` | Approved production UUID; secret-store/dashboard value only |
| `WEB_CONCURRENCY` | `2` |
| `LEAGUE_MONITOR_SERVICE` | `iac-league-production` |
| `LEAGUE_BACKUP_PREFIX` | `iac-league/` |
| `LEAGUE_BACKUP_INTERVAL_SECONDS` | `3600` |
| `LEAGUE_BACKUP_RETAIN` | `168` |
| `LEAGUE_BACKUP_BUCKET` | Approved production bucket; value not recorded here |
| `AWS_DEFAULT_REGION` | Region of the approved production stack; confirm before entry |
| `AWS_ACCESS_KEY_ID` | Approved production runtime credential; value not recorded |
| `AWS_SECRET_ACCESS_KEY` | Approved production runtime credential; value not recorded |
| `SECRET_KEY` | Preserve/enter approved production secret; value not recorded |
| `ADMIN_PASSWORD` | Preserve/enter approved production secret; value not recorded |

If temporary maintenance HTTP is required, use only the command documented in `STORAGE_RUNBOOK.md`. Never serve the repository, recovery archive or data directory.

## Pre-window preparation

These steps are safe before the window because they do not modify staging or production.

- [x] Verify the local accepted archive hash.
- [x] Verify the candidate branch and remote point to the recorded commit.
- [x] Run the complete local test suite.
- [x] Validate Python syntax, YAML syntax and whitespace.
- [x] Copied the accepted archive, manifest and acceptance record to the approved production recovery location; independent read-back matched the accepted SHA-256.
- [x] Prepare the production AWS stack parameters and change-set review worksheet locally; see `PRODUCTION_AWS_CHANGESET_WORKSHEET.md`. Create or execute the real change set only after the final staging gate and explicit GO; do not reuse staging credentials or identifiers.
- [x] Captured the deployed staging package versions without secret/environment values, committed `requirements.lock`, rebuilt staging from it, and verified exact equality plus `pip check` PASS.
- [x] Confirmed the separate operator identity can write/read production recovery evidence without runtime credentials.
- [x] Confirmed the SNS subscription and alert recipient; the operator received the labelled production delivery test.
- [ ] Confirm no admin has an import, rule edit or correction in progress.
- [ ] Export or print this checklist for the cutover operator and independent verifier.

## Cutover execution record

Execute only after GO. Follow `STORAGE_RUNBOOK.md` steps 1–8; this section is the operator control record, not a replacement for those instructions.

1. **Open maintenance and freeze writes**
   - [ ] Record production service ID, current deploy ID, commit, tier, start command and auto-deploy state.
   - [ ] Announce the freeze; receive acknowledgements from all admins.
   - [ ] Verify no import is in flight.
   - [ ] Record freeze start UTC.

2. **Preserve the recovery source**
   - [ ] Verify the accepted recovery archive SHA-256 again.
   - [ ] Verify the independent copy has the same SHA-256.
   - [ ] Record the archive location by approved storage label only; do not record credentials or signed URLs.

3. **Create persistent production storage**
   - [ ] Confirm production backup/monitoring resources and least-privilege runtime identity.
   - [ ] Disable auto-deploy without triggering an unplanned restart.
   - [ ] Upgrade the existing service and attach the approved 1 GB disk at `/var/data`.
   - [ ] Record disk ID, mount path, tier and UTC time.
   - [ ] If the empty disk prevents normal startup, use the reviewed maintenance-only start command.

4. **Restore and migrate**
   - [ ] Restore the accepted archive into an empty directory on the disk-owning instance.
   - [ ] Generate a fresh migration plan; independently review inventories and any conflicts.
   - [ ] Stop on any unexplained conflict. Never weaken validation to force the migration.
   - [ ] Apply the reviewed plan to `/var/data/league`.
   - [ ] Initialize or verify the approved volume identity.
   - [ ] Pause imports on `/var/data/league` before application verification.

5. **Start the disk-aware release**
   - [ ] Apply the frozen configuration sheet and exact release commit.
   - [ ] Start `python backup_runner.py`.
   - [ ] Confirm one supervisor, one Gunicorn master and exactly two workers.
   - [ ] Confirm the initial S3 backup returned `verified: true` and CloudWatch access succeeded.
   - [ ] Confirm the application reads from `/var/data/league`.

6. **Acceptance while imports remain paused**
   - [ ] Compare the restored inventory to the accepted manifest.
   - [ ] Verify run and walk leaderboards, athlete histories, latest result, points rules and export.
   - [ ] Record the latest actual result hash and rules/mapping hashes.
   - [ ] Restart the service and verify inventory and application output.
   - [ ] Redeploy the same commit and repeat verification.
   - [ ] Create a new verified S3 backup.
   - [ ] Restore that backup into a new empty location on an independent machine.
   - [ ] Compare every checksum, standings output and history; record recovery duration and backup age.
   - [ ] Confirm production alert state and recipient readiness.

7. **Reopen or abort**
   - [ ] Independent verifier signs PASS.
   - [ ] Owner signs GO to reopen.
   - [ ] Resume imports and announce maintenance completion.
   - [ ] Record final UTC time, deploy ID, commit, disk ID, backup key label and alarm state.
   - [ ] If any gate fails, keep imports paused and follow rollback below.

## Abort triggers and rollback

Abort immediately if the release commit/configuration differs, the mount is absent or unsupported, volume identity differs, migration reports conflicts, initial backup/read-back fails, CloudWatch access fails, worker topology is wrong, application output differs unexpectedly, independent restore fails, or the maintenance deadline is reached.

- **Before disk cutover:** make no source-content changes. Cancel the operation, retain the independent archive and lift the coordinated freeze only after the owner approves returning to the unchanged service.
- **After disk cutover:** keep imports paused and maintenance active. Preserve the disk and all evidence. Do not redeploy old `main`; it is not disk-aware. Restore the selected verified backup into a new empty directory and use a reviewed disk-aware release, or forward-fix the candidate.
- **Disk loss/corruption:** retain the damaged directory for investigation. Restore a verified S3 key onto an approved replacement disk/new empty directory, verify inventory and scoring, then switch `LEAGUE_DATA_DIR` only through a reviewed plan.
- **Unexpected data difference:** do not “fix” the evidence in place. Capture hashes and inventories, stop publication, and escalate the comparison to the owner and independent verifier.

## Evidence log

Record identifiers, hashes, counts, status and UTC timestamps only. Never record credentials, environment values, athlete data, signed URLs or operator contact details.

| UTC time | Step | Result | Safe evidence reference | Operator |
| --- | --- | --- | --- | --- |
| `2026-09-25 06:21–06:22` | Final staging dependency gate | `PASS` | `dep-dar151h42hec73cjuddg`; lock match exit 0; verified 23-file backup | Owner/operator |
| `TBD` | Production freeze | `TBD` | `TBD` | `TBD` |
| `2026-09-25 06:43–06:48` | AWS stack, identity and archive verification | `PASS` | Six-resource stack; confirmed SNS test; independent accepted-archive read-back hash matched | Owner/operator |
| `TBD` | Disk/mount/identity | `TBD` | `TBD` | `TBD` |
| `TBD` | Migration | `TBD` | `TBD` | `TBD` |
| `TBD` | Startup backup | `TBD` | `TBD` | `TBD` |
| `TBD` | Restart persistence | `TBD` | `TBD` | `TBD` |
| `TBD` | Redeploy persistence | `TBD` | `TBD` | `TBD` |
| `TBD` | Independent restore | `TBD` | `TBD` | `TBD` |
| `TBD` | Imports reopened / abort | `TBD` | `TBD` | `TBD` |

## Post-cutover

- [ ] Update `STORAGE_VERIFICATION.md` with production evidence and the P0 decision.
- [ ] Preserve the final backup and cutover evidence under the approved retention policy.
- [ ] Re-enable auto-deploy only through the normal reviewed change process.
- [ ] Schedule the first periodic production restore drill.
- [ ] After staging evidence is complete, follow the staging teardown/retention instructions in `STORAGE_STAGING.md`; teardown is a separate explicitly approved operation.
