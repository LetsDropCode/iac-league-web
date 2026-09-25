# Production AWS change-set worksheet

Prepared locally on **24 September 2026** from `ops/aws-storage.yaml.proposed` at SHA-256 `1e57fca32f52655d7264842420693aa0d4d6c44dbd9b86ba56ff222f519816de`. Updated on **25 September 2026** after creating and reviewing the unexecuted change set `production-initial-review-20260925` in `eu-north-1`.

**NO-GO:** the owner explicitly approved execution and the stack reached `CREATE_COMPLETE` on 25 September 2026. AWS storage and monitoring controls passed the checks below, but the runtime identity, independent recovery access, Render secret transfer and production cutover remain incomplete. Stack completion alone does not authorize changing Render production.

## Stack inputs

Do not record the operator's email address, credentials, account number or generated resource identifiers in this repository.

| Input | Required value / decision |
| --- | --- |
| Proposed stack label | `iac-league-production-storage` |
| AWS account | `TBD — verify interactively; do not record account number here` |
| AWS region | `eu-north-1` |
| Template | `ops/aws-storage.yaml.proposed` |
| `Service` parameter | `iac-league-production` |
| `OperatorEmail` parameter | Approved production operator; enter interactively and record confirmed/not-confirmed only |
| Execution identity | Approved operator/provisioning role, never the restricted runtime identity |

## Expected first change set

A new stack from this template should contain exactly six resource additions and no modifications or removals:

| Logical resource | Type | Required controls |
| --- | --- | --- |
| `Backups` | S3 bucket | Versioning enabled; AES256 encryption; all public access blocked; incomplete multipart uploads removed after 1 day; noncurrent versions retained 30 days; deletion and replacement retain the bucket |
| `TLSOnly` | S3 bucket policy | Deny all S3 access when `aws:SecureTransport` is false |
| `Alerts` | SNS topic | One approved email subscription; confirmation required before GO |
| `AlertPolicy` | SNS topic policy | CloudWatch publish only from the same account and matching alarm ARN |
| `BackupAlarm` | CloudWatch alarm | `IACLeague/Storage`, `BackupHealthy`, service dimension `iac-league-production`, Minimum, 30-second period, 3/3 breaching, threshold below 1, missing data breaching, ALARM and OK actions to SNS |
| `RuntimePolicy` | IAM managed policy | Bucket listing restricted to `iac-league/*`; object get/put/delete only under that prefix; CloudWatch metric write only to `IACLeague/Storage` |

Stop review if the change set includes any replacement, removal, broad IAM principal, public bucket access, generated access key, IAM user, compute resource, Render resource, Lambda function, or resource outside the six listed above.

## Pre-execution review

- [x] Final staging stale-backup and recovery evidence is PASS.
- [x] Owner authorized creation of the production change set.
- [x] Selected AWS account and `eu-north-1` region match the approved production destination.
- [x] Template hash matches the value at the top of this worksheet.
- [x] Parameters contain `Service=iac-league-production` and the approved operator email; the address matched staging without being displayed or recorded.
- [x] Change set contains six additions, zero modifications and zero removals.
- [x] The new stack uses a generated bucket with no hard-coded staging name or identifier.
- [x] Runtime policy cannot modify bucket policy, version history, SNS, alarms or IAM.
- [x] S3 bucket and object ARNs in the runtime policy resolve only to the new production bucket and `iac-league/*` prefix.
- [x] Alarm dimension is production, not staging.
- [x] SNS destination is the approved production operator.
- [ ] Independent recovery access will use a separate operator identity, not the application runtime credentials.
- [ ] Reviewer records GO in the private operational change record.

Review evidence at **2026-09-25 06:32 UTC**: change-set status `CREATE_COMPLETE`, execution status `AVAILABLE`; actions were Add-only for `AlertPolicy`, `Alerts`, `BackupAlarm`, `Backups`, `RuntimePolicy` and `TLSOnly`. The placeholder stack status was `REVIEW_IN_PROGRESS` and its resource count was zero.

## Post-execution verification

- [x] Stack reached `CREATE_COMPLETE` with no unexpected resources.
- [x] Bucket is private, encrypted with AES256 and versioned.
- [x] Bucket lifecycle has 30-day noncurrent-version retention and 1-day incomplete-multipart cleanup; CloudFormation retain policies match the reviewed template.
- [x] SNS subscription is confirmed; test publication was accepted by SNS. Delivery confirmation remains with the operator.
- [x] Alarm is present with 30-second, 3-of-3 and missing-data-breaching settings; it is correctly `ALARM` before production emits a healthy metric.
- [ ] Runtime policy is attached only to the approved production runtime principal.
- [ ] Runtime principal has console access disabled and no unrelated policies.
- [ ] One production access key is transferred directly to the approved secret store; values are never printed or recorded.
- [ ] Independent operator access can list/read backup evidence without using runtime credentials.
- [ ] Render secret variable names are prepared, but values are not saved until the approved cutover sequence calls for them.
- [ ] Safe output labels—bucket, runtime-policy ARN and alarm name—are recorded in the private change record.

## Abort and cleanup

If review fails before execution, delete the unexecuted change set and leave production unchanged. If stack creation fails, preserve events for diagnosis and do not weaken controls to make it pass. Because the bucket uses `DeletionPolicy: Retain`, stack deletion is not full data deletion; retained storage requires a separate, explicit retention/deletion decision.

Execution evidence at **2026-09-25 06:36–06:40 UTC**: all six expected resources reached `CREATE_COMPLETE`; all four S3 public-access-block controls were true; encryption was `AES256`; versioning was enabled; lifecycle values were 30 and 1 days; the alarm used namespace `IACLeague/Storage`, metric `BackupHealthy`, service `iac-league-production`, period 30, evaluation 3/3, threshold below 1 and missing-data breaching. No credentials, account number, email address, bucket name, topic ARN or access-key value are recorded here.
