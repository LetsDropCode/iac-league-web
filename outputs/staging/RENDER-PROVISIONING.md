# Render isolated staging provisioning evidence

Observed on 22 September 2026. This is staging-only; production service `srv-d6je0rf5r7bs73f07cp0` was not edited.

- New service: `iac-league-storage-staging`, ID `srv-dap9at8473hc73dh0gn0`, Oregon, connected to `LetsDropCode/iac-league-web` branch `codex/storage-durability`.
- First deploy: `dep-dap9atg473hc73dh0i1g`, commit `43f469090585afe678536df70556f3785e12cee4`, dashboard timestamp 22 September 2026 14:49:26 UTC, status `Deploy succeeded`, duration 1m08s. Trigger: First Deploy.
- Compute: `0.5c-512mb` ($7/month list price). One persistent disk configured at `/var/data`, 1 GB ($0.25/GB-month list price). The service shell reported `/var/data` on `/dev/nvme25n1[/data]` as `ext4`; the configured disk identity is intentionally omitted.
- The first start command served only `League staging maintenance` from `/tmp/league-maintenance`; Auto-Deploy remained Off. HTTP GET of the staging root returned 200 with that exact 26-byte response.
- Twelve non-secret staging environment variables and the four secret variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ADMIN_PASSWORD` and `SECRET_KEY` were entered. Only their names were verified; values and operator contact information are omitted here.
- The disk was seeded through `ops/staging_probe.py` with the labelled synthetic baseline. A post-redeploy inventory contained nine managed files. This proves the seed survived a Render redeploy; no synthetic result CSV had been imported yet.
- A manual real-S3 backup initially failed safely with `NoCredentialsError` because the existing instance predated the saved environment values. After redeploy `dep-dapdaphsrm7s73f2uej0` loaded the variables, a manual backup uploaded `iac-league/20260922T192610509572Z-33bf5f766cd243d5ba420e40ccadb6bd.zip`, SHA-256 `2c955d325e80a80acd35fcc4d1aae7567e531431260fdeceab576b20d74a7a8f`, nine files, and returned `verified: true` after a full S3 read-back.
- The start command was then changed to `python backup_runner.py`. Manual deploy `dep-dapdd9kja7ms73aueufg` of documentation-only successor commit `dc810793e4c2fd6ca8f3c0e295969b42a522b23f` succeeded in 1m10s. A public request reached the Gunicorn origin, confirming that the fail-closed startup backup and CloudWatch credential check completed before the listener opened. The service shell showed one Python supervisor (PID 60), one Gunicorn master (PID 79), and exactly two workers (PIDs 96 and 97). A second `python backup_runner.py` failed with `Another backup scheduler owns this data directory.` and exit status 1, proving the disk-backed singleton lock was held.

The approved seven-day maximum staging lifetime ends on 29 September 2026. Resource creation and the startup backup are not a complete durability pass. Next gate: import the labelled synthetic CSV through the real UI, then complete restart/redeploy, scheduled-backup, independent-restore and alert-delivery tests.

The production service was not edited, restarted, redeployed, upgraded or given credentials during these staging operations.
