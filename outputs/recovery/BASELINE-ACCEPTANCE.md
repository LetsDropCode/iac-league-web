# Production recovery baseline acceptance

- Accepted by: repository owner
- Acceptance date: 21 September 2026 (Africa/Johannesburg)
- Accepted artifact: `local-recovery-candidate.zip`
- SHA-256: `95b2d0836e5158ee999c9ed8eedda5843ad5c27f0aa51ffd959baaa23f610221`
- Purpose: authoritative baseline for staging rehearsal and production migration to persistent storage

The owner explicitly accepted the committed local recovery candidate as the authoritative production baseline.

This is an operational acceptance of the best verified recovery source available. It does not represent or imply a byte-for-byte export of the inaccessible Render Free ephemeral filesystem. Public reconciliation proves that the candidate reproduces all captured runner and walker standings and displayed scoring rules. Athlete-history reconciliation currently covers 50 of 233 profiles with no differences; 183 runner profiles remain unchecked. Unknown rejected rows, overwritten uploads, intermediate corrections, or files not represented in the public application may be absent.

Production remains unchanged by this acceptance. The archive must be copied to independent recovery storage and verified by SHA-256. Staging persistence, backup, monitoring, and independent restore tests must pass before any production restart, redeploy, disk attachment, environment change, or cutover.
