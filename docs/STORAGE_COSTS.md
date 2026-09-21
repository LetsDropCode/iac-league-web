# Proposed incremental costs and single approval scope

**Approved by the owner on 21 September 2026, subject to the limits and gates below. Isolated AWS staging resources were provisioned in Europe (Stockholm), `eu-north-1`, on 21 September; no Render staging or production resources have yet been changed.** Rates checked 2026-09-19, USD excluding tax, card fees and currency conversion. The detailed estimate used US East pricing and therefore remains conservative preparation rather than verified Stockholm billing. The new AWS account reports promotional credits; the approval does not rely on them. Authenticated dashboard inspection verified production is currently Free in Oregon with no disk. Live snapshot size remains unknown because Free provides no shell/SSH access.

## Fixed rates

| Resource | Proposed quantity | Monthly list cost (USD) |
| --- | ---: | ---: |
| Render Starter (`0.5c-512mb`) | One service instance; two processes inside it | 7.00 |
| Render persistent disk | 1 GB at `/var/data` | 0.25 |
| AWS CloudWatch custom metric | One `BackupHealthy` series per environment | 0.30 |
| AWS CloudWatch standard alarm | One alarm per environment | 0.10 |
| CloudWatch PutMetricData | 43,200 calls/30-day month at $0.01/1,000 | 0.432 |

Render's current [pricing](https://render.com/pricing) also lists marginal outbound bandwidth at $0.15/GB and Hobby build overage at $5/1,000 minutes. Workspace fees remain unchanged; no Pro workspace upgrade is proposed. The [compute-plan reference](https://render.com/docs/compute-plans) confirms legacy `starter` remains valid. Check actual account allowances and proration before provisioning.

AWS's current published price-list extracts, dates and source URLs are saved in [STORAGE_PRICING_EVIDENCE.json](STORAGE_PRICING_EVIDENCE.json). The [CloudWatch pricing page](https://aws.amazon.com/cloudwatch/pricing/) has inconsistent API-request wording between its summary and examples; this estimate uses the public regional price list's $0.01/1,000 rate, before free allowances. At one report per minute, the estimate includes $0.432 even if the account's free request allowance ultimately covers it.

## Variable backup costs

For [S3 Standard](https://aws.amazon.com/s3/pricing/) in the assumed region, the current first-tier rates are $0.023/GiB-month storage; PUT/COPY/POST/LIST $0.005/1,000; GET $0.0004/1,000; DELETE is free. Each verified backup performs a PUT, full GET read-back and normally one LIST. At 720 backups/month, that is approximately **$0.007488/month** in these requests, excluding extra startup backups, pagination, retries, console browsing and restore drills.

Use compressed complete archive size **A in GiB**, not the size of the newest upload. It includes all results, rules, mappings, prior versions and journal records. With 168 current hourly snapshots plus 30 days of recoverable noncurrent versions after application retention deletes keys, steady-state stored content is approximately **888 × A GiB**. Storage costs approximately **$20.424 × A/month**. Lifecycle cleanup is asynchronous; version growth, failed uploads and repeated restarts can increase this estimate.

The scheduler uploads about `720 × A` GiB/month from Render and reads the same amount back from AWS. At marginal rates, that is approximately `$115.964 × A` Render egress (conservatively treating its billed GB as 10^9 bytes) and `$64.80 × A` AWS internet egress per month. The AWS [regional transfer price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/us-east-1/index.json) gives $0.09/GiB for the first charged outbound tier; available global free transfer allowances may reduce this. AWS inbound transfers are not an added storage retrieval charge. No Transfer Acceleration, KMS key, cross-region replication or access-log stream is proposed. Extra full restores/downloads incur GET and transfer costs.

[SNS operator email](https://aws.amazon.com/sns/faqs/) marginal rates are $0.50/million requests and $2/100,000 email deliveries before allowances. One incident plus recovery is tiny but not assumed literally free. The operator must confirm the subscription. CloudWatch evaluation/notification continues independently of Render; no separately billed cron service is required.

## Incremental scenarios

Approximate 30-day incremental total from the **verified existing Free service**, with one production environment and before any allowances:

`$8.089488 + $201.188 × A + extra requests/alerts/builds/web traffic/taxes`

| Compressed full snapshot | Approximate incremental USD/month |
| --- | ---: |
| 1 MiB | 8.29 |
| 10 MiB | 10.05 |
| 100 MiB | 27.74 |

There is no existing paid compute or disk charge to subtract. Exact variable backup cost still requires the current live archive size and selected AWS account/region. The proposed 512 MB Starter plan preserves current RAM while increasing CPU; staging must establish peak memory because complete archives are assembled in memory.

The 41,482-byte archive measured locally is **repository data, not live data**; it must not be used to price the live uploads. Before approval is acted upon, record actual live file count/bytes and independently captured archive size; also test peak memory on the 512 MB instance. Full archives are currently assembled in memory, so compressed size alone does not establish memory safety.

## Staging costs, separately

One isolated Starter instance plus 1 GB disk is another **$7.25/month equivalent**. Metric/alarm is another $0.40/month and minute reporting up to $0.432/month before allowances, plus its own S3/request/transfer costs. Seven days of this fixed baseline is approximately **$1.89** assuming 30-day proration. Synthetic fixtures are tiny; proposed **one-time staging budget: $3 excluding tax**, with no runtime extension beyond seven days without approval. Additional builds and retained S3 evidence can outlive the service. CloudFormation retains the S3 bucket on teardown; arrange explicit finite staging evidence retention/deletion. A budget is not an automatic hard billing cap.

## Approved scope

The owner approved the following scope on 21 September 2026:

> Approve one isolated seven-day synthetic staging service/disk and separate AWS staging backup/alert resources, budget US$3 excluding tax; approve the existing production service's one-instance Starter-equivalent configuration with a 1 GB `/var/data` disk, private versioned S3 backups (168 current snapshots, 30-day noncurrent recovery), one CloudWatch metric/alarm and SNS notifications, targeting no more than US$15/month **incremental** excluding tax. Authorize the runbook's maintenance-window production cutover only after authenticated settings inspection, safe current-live-data access, an independently verified live backup/restore, staging acceptance, and review of the final checksum migration plan. Authorize sending the staging failure/recovery tests and subsequent operational alerts only to the operator destination I supply. Do not proceed if costs/capacity exceed this envelope or current tier would be downgraded; return with a revised estimate. Do not restart, redeploy, attach a disk, change production environment/start commands, or otherwise endanger ephemeral live files before the live backup gate passes.

This is conditional authorization, not permission to bypass any failed gate. Configure billing alerts in the existing billing system; usage charges cannot be hard-capped by this proposal. AWS account/region, Render billing readiness, operator alert destination, maintenance window and import-freeze owner still require confirmation. Actual interruption duration will be measured in staging, not promised before testing.
