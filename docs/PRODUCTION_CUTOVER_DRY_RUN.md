# Production cutover local dry run

Run at **2026-09-24 18:34–18:37 UTC** against candidate commit `01d2915ac52a2519007313ca369cb417d6953007`. This was a local tabletop exercise in a disposable directory. It did not contact or change Render, AWS, staging or production, and it is not a substitute for the production independent-backup and restore gates.

## Recovery source

- Accepted archive: `outputs/recovery/local-recovery-candidate.zip`
- Archive SHA-256: `95b2d0836e5158ee999c9ed8eedda5843ad5c27f0aa51ffd959baaa23f610221`
- Archive contents: 30 managed source files, 156,653 uncompressed bytes
- Per-file hashes: all 30 matched `outputs/recovery/manifest.json`

The first inventory command intentionally used `/tmp`, which macOS resolves through `/private/tmp`; storage validation correctly rejected the non-canonical spelling. Re-running with the canonical `/private/tmp` path passed. Production paths in the frozen configuration are already canonical Linux paths under `/var/data`.

## Migration rehearsal

| Check | Result |
| --- | --- |
| Source managed files | 30 |
| Planned copies | 30 |
| Conflicts | 0 |
| Local production-format backup size | 40,431 bytes |
| Migration duration | 0.014730 seconds |
| Source files verified in destination | 30/30 |
| Disposable volume identity initialization | PASS |
| Shared import pause | PASS |
| Shared import resume | PASS |

The migration plan was generated before apply. Apply used an independently generated production-format snapshot of the source and rechecked the reviewed plan, source hashes and destination hashes. The migration added its audit record; initialization then added the disposable storage identity.

## Application verification

The migrated directory was selected only through `LEAGUE_DATA_DIR` in a fresh local process.

| Check | Result |
| --- | --- |
| Excel export generation | PASS |
| Runner leaderboard | 211 athletes, 2,316 total points |
| Walker leaderboard | 22 athletes, 553 total points |
| Managed files after migration/identity | 32 |

Console row counts produced while processing individual race rows were 511 run rows and 73 walk rows; these are event-result rows, not unique athlete counts.

## Backup/restore rehearsal

A new production-format backup was generated from the migrated directory and restored into a separate empty local directory.

| Check | Result |
| --- | --- |
| Backup archive size | 43,318 bytes |
| Managed files | 32 |
| Restore duration | 0.015425 seconds |
| Exact source/restored inventory equality | PASS |

This proves the candidate tooling can migrate and restore the accepted archive locally. It does not demonstrate real production S3 access, a Render disk mount, cross-machine recovery, alerting, or production capacity.

## Dependency audit

`pip check` reported no broken requirements in the local Python 3.9 environment. Direct dependency versions observed locally were:

| Package | Local version |
| --- | --- |
| Flask | 3.1.3 |
| pandas | 2.3.3 |
| flask-limiter | 3.11.0 |
| flask-seasurf | 2.0.0 |
| flask-talisman | 1.1.0 |
| bleach | 6.2.0 |
| gunicorn | 23.0.0 |
| openpyxl | 3.1.5 |
| requests | 2.32.5 |
| beautifulsoup4 | 4.15.0 |
| lxml | 6.1.3 |
| boto3 | 1.42.97 |

The local environment above was not used as the production dependency definition. On 25 September 2026, the exact package set from the verified Render staging Python 3.14.3 runtime was captured in `requirements.lock` at SHA-256 `d5dfdac6d9c735b6442601ba0d53b05fe1eef5c4307ecc15d35440de313e3846`. Candidate commit `42a6adfe2bd836930302759709dcdab7c70b1f0a` was deployed from that lockfile as Render deploy `dep-dar151h42hec73cjuddg` in 1m24s.

Post-deploy verification reported no broken requirements, and comparison of the installed runtime package set (excluding only `pip` and lockfile comments) to `requirements.lock` returned exit 0. The service retained the expected one backup supervisor, one Gunicorn master and two workers. A fresh 23-file backup returned `verified: true` under key label `iac-league/20260925T062157383193Z-b5155ea9457a408cb8cda2b075c229dd.zip`. This closes the dependency-reproducibility staging gate; it does not authorize or demonstrate the production cutover.
