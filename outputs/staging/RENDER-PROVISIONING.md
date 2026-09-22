# Render isolated staging provisioning evidence

Observed on 22 September 2026. This is staging-only; production service `srv-d6je0rf5r7bs73f07cp0` was not edited.

- New service: `iac-league-storage-staging`, ID `srv-dap9at8473hc73dh0gn0`, Oregon, connected to `LetsDropCode/iac-league-web` branch `codex/storage-durability`.
- First deploy: `dep-dap9atg473hc73dh0i1g`, commit `43f469090585afe678536df70556f3785e12cee4`, dashboard timestamp 22 September 2026 14:49:26 UTC, status `Deploy succeeded`, duration 1m08s. Trigger: First Deploy.
- Compute: `0.5c-512mb` ($7/month list price). One persistent disk configured at `/var/data`, 1 GB ($0.25/GB-month list price). Dashboard disk ID and actual mount device have not been captured.
- Start command serves only `League staging maintenance` from `/tmp/league-maintenance`; Auto-Deploy is Off. HTTP GET of the staging root returned 200 with that exact 26-byte response. No application upload UI or backup supervisor is active yet.
- Twelve non-secret staging environment variables were entered, including the staging volume UUID, bucket, region and backup settings. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ADMIN_PASSWORD` and `SECRET_KEY` were not entered. Credential values and operator contact information are omitted here.
- The Render web shell displayed an empty black terminal in Safari after the successful deployment. Attempts to run a read-only `pwd` or `stat` did not yield output. The disk has therefore **not** been seeded; no mount-device, file-inventory or runtime-process claim is made.

The approved seven-day maximum staging lifetime ends on 29 September 2026. Resource creation is not a durability pass. Next gate: obtain a working disk-owning shell, verify the mount, seed only the labelled synthetic fixture, enter the remaining application secrets directly in Render, and then deploy the supervisor on the same reviewed commit for end-to-end tests.

Subsequent update on 22 September 2026: the owner entered `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in the isolated staging environment. Both variable names were verified in Render's saved list without inspecting their values; the production environment did not show those names. The first maintenance deploy remained Live. The Safari web shell eventually displayed a prompt after reconnecting, but automated command input did not reach the terminal; no disk command was executed. `ADMIN_PASSWORD` and `SECRET_KEY` remain outstanding.
