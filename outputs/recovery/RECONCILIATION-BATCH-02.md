# Athlete-history reconciliation — batch 02

Batch 02 checked **10 additional runner profiles** and **27 race/time/points rows**. It found **0 differences**.

The reconciliation now covers **50 of 233 athlete profiles**: all 22 walkers and 28 runners. **183 runner profiles remain.**

The live application returned `429 Too Many Requests — 50 per 1 hour` on the eleventh request in this continuation because the earlier reconciliation still occupied part of the rolling window. Requests stopped immediately. No retry, bypass, alternate address, production write, upload, setting change, deployment, or paid resource was used.

This batch is stored separately so the original 40-profile evidence and original remaining-path list remain unchanged. Resume only from `remaining-history-paths-after-batch-02.json` after the rolling window resets.

P0 remains open. Matching public histories strengthen the local recovery candidate but do not prove byte-for-byte equivalence with the inaccessible live filesystem.
