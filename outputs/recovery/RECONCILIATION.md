# Recovery reconciliation — 19 September 2026

**All captured standings and displayed rules match. Full finish-time reconciliation is incomplete. P0 remains open.**

| Check | Result |
|---|---|
| Local source preservation | 27 CSV result files plus 3 rules/mapping files archived; all 30 file SHA-256 checksums verified by reading the archive back |
| Runner standings | All 211 profiles match; no missing or extra profiles |
| Walker standings | All 22 profiles match; no missing or extra profiles |
| Fields compared | Names, gender, overall rank, category rank, races completed, total points and every race-distance points column; identity matched using profile URLs |
| Public scoring rules | All 1,898 displayed rows match, including duplicate multiplicity |
| Athlete finish-time histories | 40 profiles checked: 22 walkers and 18 runners; 118 race/time/points rows; 0 differences |
| Remaining histories | 193 runner profiles not checked |

## Interpretation

The local candidate reproduces all currently captured public standings, not just leading scores. The history sample additionally matches finish times. This substantially strengthens the case for using the local files as a recovery baseline, but it does not certify an exact copy of the live filesystem or preserve unknown rejected rows, duplicates, overwritten uploads or intermediate corrections.

The complete live standings were captured from all browser table pages; public rules were captured across 19 pages. Runner histories were sampled at every eleventh displayed runner, taking 18 profiles; all walker histories were checked. Checks used the deployed baseline scoring code, extracted locally from commit d285886d4347e11578a5667ff4870f7c035b95fe. No scoring corrections were applied. Category is encoded in the profile identity; the website hides its category table column. Rank Change was excluded because it depends on filesystem modification times. Page-request time is not a publication timestamp.

The application configures 50 requests/hour and 200/day for public endpoints. History retrieval was deliberately bounded to 40 profiles to leave headroom. No limit was bypassed, and no HTTP 429 was observed. Completing the remaining histories requires later permitted request windows; no scheduled task was created. Saved remaining paths provide an exact resume list.

The site initially displayed Render's service-wake-up page; it subsequently served the league. Evidence describes the public state at the capture timestamps, not any earlier ephemeral state. Multi-page captures are not a transactional live snapshot.

## Preserved files

- `local-recovery-candidate.zip`: source files only; not a live export or an independent off-device backup.
- `manifest.json`: SHA-256 checksums and source-archive checksum.
- `public-run.json`, `public-walk.json`: complete captured standings.
- `public-rules.json`: complete displayed rules.
- `public-histories.json`: captured history rows and page text.
- `comparison.json`: machine-readable comparison results.
- `remaining-history-paths.json`: unfinished profile checks.

The previous 31-file restore report used a different inventory. This archive deliberately preserves the 30 input files: 27 results and 3 rule/mapping files. It does not include a generated Excel export.

## Next step

Resume the remaining finish-time checks in permitted request windows if full public-history reconciliation is required. Do not describe that step as completed. The owner has not yet accepted the candidate as authoritative. Any eventual acceptance must acknowledge that full public equivalence still cannot prove every original source byte.

No repository files, production settings, uploads, deployments or paid resources were changed. The existing storage branch and its uncommitted documentation changes were left untouched. P0 closure still requires proven persistent storage and independent restoration.
