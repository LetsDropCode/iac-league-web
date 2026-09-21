# AWS staging provisioning evidence

- Region: Europe (Stockholm), `eu-north-1`
- Stack: `iac-league-staging-storage`
- Stack completion: 21 September 2026 at 19:13:08 UTC
- Deployed template: `ops/aws-storage.json`
- Deployed template SHA-256: `a45a0f53e8fba7183e09fd73cee09d3a5bbf05f7861d60ba60f7d97ad5b2ac37`
- Change-set review: six additions; no modifications, replacements, or deletions
- Stack status: `CREATE_COMPLETE`

All six expected resources reported `CREATE_COMPLETE`: an encrypted/versioned S3 bucket, its TLS-only bucket policy, an SNS topic, its CloudWatch-only topic policy, a missing/failure CloudWatch alarm, and a restricted IAM managed policy. The stack exposed the expected bucket, alarm-name, and runtime-policy outputs. Physical names, the AWS account identifier, and the operator email are intentionally omitted from repository evidence.

The runtime policy is not attached to a principal, no access keys were generated, and no Render resources or production resources were changed. The AWS console also stored the uploaded deployment template in its account-managed `cf-templates` bucket; it contains no parameter values or credentials.

The AWS SNS console showed the operator email subscription as `Confirmed` on 21 September 2026. The address is intentionally omitted. Confirmation proves the subscription is active, but not yet that alarm notifications are delivered. The alarm is expected to enter `ALARM` while staging emits no `BackupHealthy` metric; this is intentional missing-monitor coverage, not proof of a working backup.
