# Hosted-first CI with AWS fallback

Public repositories always select free standard Ubuntu hosted runners. For private repositories, `KORZ_RUNNER_BACKEND=github` selects standard Ubuntu hosted runners in the migrated workflows. Any other value preserves each job's AWS/default runner. The AWS controller owns the organization variable; repository variables override it for canaries or rollback.

| Variable | Value after AWS canary | Purpose |
| --- | --- | --- |
| `KORZ_SECURITY_RUNNER_LABELS` | `"korz-cloud-security"` (JSON string) | Native Semgrep, 1 CPU / 2 GB |
| `KORZ_UTILITY_RUNNER_LABELS` | `"korz-cloud-utility"` (JSON string) | Administrative jobs, 0.5 CPU / 1 GB |
| `KORZ_RUNNER_BACKEND` | `github` or `aws` | Automatic preference; unset preserves existing routing |

## Activation order

1. In infraestructure, build and push `base` and `security` with `app/stacks/ci-runners/image/build-push.sh`, then review and apply the ci-runners Terraform plan. Routing is disabled by default.
2. Release the native Semgrep action. Existing container callers still work. Run one security workflow with the same rules and compare targets, findings, exit status, and total task duration.
3. Preview consumer changes: `python3 scripts/route-runners.py /path/to/repo`. Use `--write` only in a clean feature branch, review the diff and run the repo's checks. The tool preserves triggers, check names, language packs and exclusions. It covers security and the shared x64 CI/build workflows; custom workflows and ARM builds require explicit review.
4. Set the profile variables for one migrated repository and run an AWS canary. Then set that repository's backend to `github` and prove a hosted job can start. Remove its backend override when ready for automatic routing.
5. Confirm the PAT referenced by the AWS controller can read organization billing and read/write organization Actions variables. Enable `hosted_runner_routing` in the ci-runners stack only after these checks. Widen the profile variables/migration to other repositories gradually.

The controller polls every five minutes from Lambda, so it does not consume hosted minutes to decide where jobs run. The included quota is configuration (3000 for the current Team plan). It uses the current UTC month, ignores storage, and conservatively routes unknown minute SKUs to AWS. Review the quota and accounting before using other operating systems or plans.

## Limits and rollback

The default threshold is 10 reserved minutes plus 90 minutes of headroom. Setting headroom to zero implements a literal 10-minute threshold, but concurrent/in-flight jobs and reporting delays can exhaust that reserve. This is routing, not a spending cap. It does not migrate an already queued/running job or retry deployments on another backend.

Billing errors select AWS if writing the variable still works. A dead controller, expired PAT or failed variable update can leave the last value in place: monitor Lambda errors and use GitHub's billing budget as the independent spending limit. Check for per-repo variable overrides if a repo ignores the organization setting.

Rollback routing by setting a repository backend to `aws`, or disabling the controller and setting the organization backend to `aws`. Unset the two profile variables to return to old AWS labels. Do this before removing task definitions/images. Native Semgrep can keep running on the prior CodeBuild/hosted runner; restore its former container if needed.

## Extending and verifying

Add a named profile in Terraform's `runner_profiles`. Its task family, allowed webhook label and ECR retention are derived from that map. Add a Dockerfile target only if it needs different tools; the image build script discovers targets. Existing toolchain/database labels cannot be overwritten.

Local checks: `python3 -m pytest scripts -q` here, and `python3 -m pytest app/stacks/ci-runners/lambda -q` plus Terraform fmt/validate in infraestructure. Measure AWS task time including image download and CodeBuild's rounded minutes against comparable jobs; GitHub step durations alone are not the bill.
