# Render support request and response

Subject: Non-restarting export of ephemeral files before persistent-disk upgrade

We need to preserve current user-uploaded files from Render web service `srv-d6je0rf5r7bs73f07cp0` (`iac-league-web`, Oregon). The service is currently on the Free plan with no shell/SSH or persistent disk. Its application writes mutable data under the deployed source directory, including `results/`, `points_rules.csv`, `points_rules_walk.csv`, and `category_map.csv`.

Upgrading or redeploying before export could replace the current ephemeral filesystem and lose uploads. We will not upgrade, restart, redeploy, change commands/environment, or attach a disk until we have an independently verified backup.

Can Render provide a supported way to read or export those paths from the **currently running instance without restarting or replacing it**? A temporary read-only shell/SSH session or a Render-assisted archive would work. Please confirm explicitly whether the proposed method triggers any restart, redeploy, instance replacement, or filesystem reset before we use it.

We do not need Render to inspect file contents. We need byte-preserving access so we can inventory names, sizes and SHA-256 checksums, upload an encrypted independent backup, restore it elsewhere, and only then schedule the paid-plan/disk cutover.

Please do not trigger a restart, deploy, upgrade, disk attachment, or service replacement while investigating this request.

Record the support case identifier and Render's exact response in `STORAGE_VERIFICATION.md`. Do not paste credentials, secret values, athlete details, file contents, or private deploy-hook URLs into the case.

## Response observed 2026-09-19 18:14 UTC

A screenshot supplied by the application owner shows a response in the Render dashboard support panel. It states that there is no supported way to access the filesystem of a running Free web service without restarting or replacing it. It also states that:

- the filesystem is ephemeral and files written after boot are lost when the service restarts, redeploys or spins down;
- Free services cannot attach persistent disks;
- `render ssh` requires a paid service; and
- the safest route is to copy/archive files from within the application before any restart or deployment.

No support case identifier or evidence of human escalation is visible in the screenshot. Treat this as provider guidance recorded from the dashboard, not authorization to change the service. The currently deployed application has not been shown to expose a byte-preserving export of every managed result, rules file, mapping and publication record. Adding such an export would require a deployment and therefore cannot safely recover unknown files already present only on the current ephemeral instance.
