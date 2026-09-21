# Isolated staging verification plan — AWS provisioned; Render pending

Use `ops/render.staging.yaml.proposed` and the deployed `ops/aws-storage.json` stack with `Service=iac-league-staging`. No production data or credentials. This is a real Render disk and independent AWS S3 test, not a local-directory substitute. The owner approved the costs in STORAGE_COSTS.md. Maximum planned lifetime is seven days. Keep all resources isolated from production.

## Missing prerequisites

The implementation and recovery evidence are committed and available on `codex/storage-durability` at `9ecedef`; later documentation-only commits record approvals and provisioning. The staging fixture is `tests/fixtures/synthetic.csv`, SHA-256 `e8df6d47b2dc6b27c6ffef62188102324b7aae166b2f5a91bf7a21f5ef287c00`. It is a labelled synthetic baseline and is not a production recovery source.

AWS provisioning completed in `eu-north-1` on 21 September 2026; see `outputs/staging/AWS-PROVISIONING.md`. These external prerequisites remain before Render provisioning and end-to-end testing:

- The SNS email subscription is confirmed; alarm delivery testing remains outstanding.
- Create or select a staging-only AWS runtime principal and attach only the stack's restricted runtime policy. Put its credentials into Render's secret environment settings; do not send them in chat or commit them.
- Render account permission and billing configuration to create the isolated paid service/disk. The authenticated production inspection does not itself prove this permission or authorize charges.
- A staging-only volume UUID, admin password and application secret generated outside Git and entered directly in Render's secret settings.
- Independent recovery access to the staging S3 bucket on a separate machine, configured through an AWS profile/SSO or another approved secure credential mechanism.

The staging Blueprint now targets the implementation branch and intentionally starts in maintenance mode. Verify its first deployed commit is the exact hash above, seed the mounted disk, configure secrets, then change only the staging start command to `python backup_runner.py` and deploy that same commit. Do not point this Blueprint at `main` or production.

## Provision after approval

1. Confirm AWS account/region and approved operator alert address. Review the CloudFormation change set for a private versioned bucket, encryption, TLS-only access, noncurrent-version lifecycle, restricted runtime policy, SNS email subscription and CloudWatch alarm. Provision with an operator identity; the runtime principal cannot change alarms, bucket policy or old object versions. No access keys are generated in the template. Store credentials in Render environment secrets and keep independent recovery access. Confirm the SNS email subscription outside this task and record only confirmed/not-confirmed in evidence.
2. Create the isolated Render service/disk. Starter/`0.5c-512mb` (legacy `starter` remains supported), one instance, two Gunicorn workers, 1 GB `/var/data`, auto-deploy off. First use the maintenance start command from the production runbook; do not weaken mount checks for initialization. Set the variables from the staging proposal, a staging-only volume UUID, separate admin password/secret, and staging bucket credentials. Use `LEAGUE_ENV=production` even in staging so the real durability checks run.
3. Commit the reviewed implementation and deploy that **exact commit**. Record the actual Render deploy ID/commit/time; a local HEAD with uncommitted changes is not a deployed implementation identifier. From the disk-owning service shell, seed the empty data directory explicitly:

   ```sh
   python ops/staging_probe.py seed --root /var/data/staging-league
   ```

   This refuses non-staging environments and nonempty destinations. It creates only synthetic rules/mappings and the staging identity, leaving results empty. Set start command to `python backup_runner.py`. Startup requires a verified S3 backup and successful CloudWatch metric call before Gunicorn starts. Confirm there is exactly one supervisor and two workers. Confirm `.backup-scheduler.lock` remains held and a second `python backup_runner.py` exits with the duplicate-scheduler error (do not terminate the real supervisor).
4. Capture `stat` device IDs for `/var/data/staging-league` from the supervisor and shell and compare Linux mount-table path/filesystem to the Render disk settings. The scheduler runs **inside the same service instance**, using the same `get_storage()` as the app, before spawning workers; it is not a separate cron service. Wait for an actual scheduled hourly backup (not just startup) and download it to an independent machine; its manifest must include the imported synthetic file's hash. These are the required live-disk/scheduled-execution demonstrations.

## Acceptance sequence and evidence

Use UTC timestamps. Record only file hashes/counts, aggregate synthetic standings digests, worker counts/PIDs and deploy/disk identifiers. Do not copy credentials into evidence.

| Step | Action | Required observation |
| --- | --- | --- |
| Import | Sign into staging; upload `tests/fixtures/synthetic.csv` through the real upload UI | One synthetic runner, 20 points; journal committed |
| Checkpoint | `python ops/staging_probe.py record --root /var/data/staging-league --checkpoint /var/data/before-restart.json` | Save aggregate checksums; copy evidence off service |
| Restart | Restart **staging only** from Render; run probe `verify` with the checkpoint | Same files/rules/mappings/standings; new serving PIDs |
| Redeploy | Redeploy the exact same reviewed commit; repeat probe `verify` | Identical hashes/standings after actual deployment |
| S3 restore | Use `storage_ops.py backup --source /var/data/staging-league --retain 168`; restore its returned key on an independent machine into an empty directory | Remote read-back succeeds, probe `verify` matches checkpoint; no local archive substitution |
| Invalid/interrupted | Run focused storage tests against disposable temporary fixtures on staging, never fault-inject into production | Invalid input and failure before target replacement preserve prior bytes; failure after replacement retains prior/new versions and recoverable journal |
| Correction | `python ops/staging_probe.py correct --root /var/data/staging-league` | 10 points; repeated HTTP requests and PID-only Gunicorn access log prove **both existing worker PIDs** serve corrected totals |
| Rollback | `python ops/staging_probe.py rollback --root /var/data/staging-league` | Both workers return 20 points; correction bytes and journal retained |
| Import freeze | `python storage_ops.py pause-imports --source /var/data/staging-league`; try a new upload; then `resume-imports` | All workers reject publication while marker exists; normal imports resume afterward |
| Backup failure | Temporarily deny `s3:PutObject` to **staging runtime principal only**, allow next scheduled attempt, then restore permission | `verified:false`, `BackupHealthy=0`, CloudWatch ALARM, confirmed operator email receipt; old verified backup remains restorable |
| Missed backup with monitor alive | In staging, hold `.storage.lock` exclusively long enough to prevent a scheduled backup for over two hours; release afterward | Monitor thread still runs, age exceeds 7200 seconds, metric goes 0, alarm/email; next verified backup clears health |
| Entire service/monitor missing | Stop staging using a maintenance deployment with no supervisor/metric emitter | Independent CloudWatch treats missing data as breaching; operator receives alarm even with app stopped |
| Recovery | Restart normal staging, allow initial and scheduled verified backups | Alarm transitions OK; capture operator recovery email; restore newest key once more |

CloudWatch configuration is one `BackupHealthy` metric every 60 seconds, Minimum < 1 for three 60-second periods, missing data treated as breaching. The emitter checks actual last verified backup age and failed status; it never sends athlete data, paths, keys or secrets. Stalled backup I/O does not block the monitoring thread. CloudWatch runs independently of Render. AWS evaluates extra historical datapoints when samples are missing, so measure actual alert latency; do not promise an exact three-minute outage notification. Target: failed backup notification within ten minutes, stale backup notification within two hours plus ten minutes, total monitor/service outage notification within ten minutes. If measured latency exceeds the target, staging fails and the alarm must be adjusted before cutover. Alerts are state-change notifications, not repeated paging; route escalation through the approved operator process.

The failure/missed-backup experiments are **not run** until approval and a confirmed alert recipient exist. Local unit tests verify the emitter's decisions only, not CloudWatch evaluation or email delivery. Do not send test alerts to an unspecified recipient.

## Rollback and teardown

The tested application rollback path is a journaled compare-and-swap publication of the prior version, and restoration into a separate empty directory. On production cutover failure, keep imports paused and serve maintenance; restore the final independent backup on the disk and restart a disk-aware release. Old `main` is not a safe code rollback because it uses relative paths. Preserve the final backup and reviewed disk-aware release before reopening imports.

After collecting evidence, stop and delete the approved synthetic Render service/disk within seven days. Staging S3 buckets have `DeletionPolicy: Retain`; their archives continue billing until an operator explicitly approves deletion or a finite staging retention policy. Remove/disable the staging alarm only after recording the intentional teardown and notifying the approved operator. Never apply production teardown actions. Keep production closed until its own live-data and persistence gates pass.
