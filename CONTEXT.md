# CONTEXT.md

Orientation for anyone — human or agent — landing in `korz-sh/central-workflows` for the first
time. `README.md` says *what is here* (and is partly out of date, see §5); this file says *how it
fits together*, *what must not be broken*, and *where the surprises are*.

---

## 1. What this repo is

The CI hub of the org. **12 files, no application code**: 9 workflows under
`.github/workflows/` and 2 composite actions under `.github/actions/`, plus the README.

Every other korz repo reaches into this one — a consumer's CI is one line pointing back here
(`entitlement-api/.github/workflows/ci.yml` — "korz-sh/central-workflows/.github/workflows/ci-dotnet.yml@main").
Two different mechanisms, and the difference matters:

| Mechanism | Files | Who calls it (verified by grep across the sibling checkouts) |
|---|---|---|
| **Composite action** (`uses: korz-sh/central-workflows/.github/actions/…@main` **in a step**) | `semgrep-scan`, `supply-chain-scan` | **12 repos** — agent-platform-api, entitlement-api, identity-api-v2, infraestructure, korz-code, korz-query-api, mcp-servers, payments-service-api, rbac-api, shared-contracts, web-api, web-client — plus this repo's own `security.yml` (13 copies of `security.yml` total) |
| **Reusable workflow** (`uses: …@main` **as a job**) | `build-docker-ecr` | 6 repos, 7 call sites (korz-query-api calls it twice) |
| | `deploy-lambda` | 6 repos: entitlement-api, identity-api-v2, korz-query-api, payments-service-api, rbac-api, web-api |
| | `ci-dotnet` | 3: entitlement-api, rbac-api, web-api |
| | `publish-ghcr` | 2: identity-api-v2, payments-service-api |
| | `ci-go` | 1: identity-api-v2 |
| | `ci-node` | 1: payments-service-api |
| | `publish-status` | **0 external callers.** Only `ci-go.yml:157` and `ci-node.yml:145` call it |
| **Not reusable at all** | `pr-check.yml`, `security.yml` | this repo's own gate (`on: pull_request` / `push`) |

**Everyone pins `@main`. There is no staging channel between a merge here and the CI of 12 other
repos** (`pr-check.yml:10-11`). That is the single fact that shapes everything else in this file.

---

## 2. What must not be broken

**The composite actions must stay composite actions.** The org ruleset *korz security gate*
(id `20664553`) requires the status contexts **`sast`** and **`supply-chain`** *by exact name*.
A reusable workflow renames its checks to `<caller-job-id> / <job-name>` — `security / sast` — so
the required contexts would stop reporting and **every PR in the org would block, starting with
the PR that made the change** (`.github/actions/semgrep-scan/action.yml:6-16`). The ruleset JSON is
transcribed in korz-dev `docs/ruleset-korz-security-gate.md`; it excludes `.github` and `korz-dev`.

**This repo's own `security.yml` must call the actions by relative path**, `./.github/actions/…`,
not `korz-sh/central-workflows/…@main` (`security.yml:40-51`). Pinning itself to its own default
branch validates a PR against the *old* copy on main — and on the PR that first added them,
against a copy that did not exist:
`Can't find 'action.yml' ... for action 'korz-sh/central-workflows/.github/actions/semgrep-scan@main'`.
Consumers still pin `@main`, which is what they want.

**`pr-check.yml`'s five rules are the only thing standing between a typo here and 12 broken repos.**
Each rule exists because a real file here violated it, and each defect had the same signature —
*0 jobs in 0 seconds, on every push, 0 successes over the file's entire life* (korz-dev
`docs/central-workflows-gate.md`). The last of the five is
`pr-check.yml` — "Every reusable workflow declares its interface":

1. every workflow parses and has a `jobs` block — **and every `action.yml` has a `runs` block and
   a `shell:` on each composite `run` step** (`pr-check.yml:66-82`); omitting `shell` parses fine
   and fails at runtime in every caller at once.
2. no check swallows its exit code — the grep covers `|| true` *and* `|| echo`, over the whole
   file rather than the `run:` line, and the step plants a swallow to prove the pattern still
   sees one (§5).
3. **no step calls a reusable workflow.** `ci-go.yml` and `ci-node.yml` both had
   `uses: …/publish-status.yml` inside a step; that makes the whole file invalid.
4. **no workflow declares `GITHUB_TOKEN`.** It is a reserved name; declaring it under
   `workflow_call.secrets` rejects the run before any job starts. That is how `publish-status.yml`
   accumulated zero successes while looking correct in the editor.
5. every `workflow_call` declares inputs or secrets.

**`pr-check.yml`'s `validate` job is deliberately pinned to `ubuntu-latest`** while everything else
follows `vars.KORZ_RUNNER_LABELS` (`pr-check.yml:25-39`). Both strategies fail somehow: pinned dies
when the hosted quota is exhausted; switched **queues forever** when the variable names self-hosted
labels with no runner registered — which is indistinguishable from "about to start". For the gate
that must report before anything can merge, failing loudly beats waiting silently.

**Deploy/publish jobs are not exempt from the runner switch, but `publish-ghcr` was — and it broke.**
`publish-ghcr.yml:32-38` records that keeping `ubuntu-latest` there is why `Publish` failed in
identity-api-v2 and payments-service-api from 2026-08-16 (`recent account payments have failed`).
README's "Deploys stay hosted, on purpose" section describes a policy the code no longer follows;
**every `runs-on` in every file except `pr-check.yml` now reads
`${{ fromJSON(vars.KORZ_RUNNER_LABELS || '"ubuntu-latest"') }}`.** The code wins.

**Production deploys are opt-in and were never real.** `deploy-lambda.yml:36-61`: `prod-branch`
defaults to `''`, disabling `deploy-prod`. Across the six consumers, **143 `deploy-prod` jobs have
run and zero ever succeeded**, and five of six still have `LAMBDA_FUNCTION_PROD` identical to
`LAMBDA_FUNCTION_STAGING` — a working prod role would have silently overwritten staging.
`staging-branch` is `required: true` with **no default** for the same reason: the old `develop`
default matched no consumer, so staging deploys silently skipped.

**No `cache: true` on any language setup action, anywhere.** `actions/cache` restores with `tar -P`
(absolute paths) into the workspace and took the checkout with it — `MSBUILD : error MSB1003:
Specify a project or solution file.` after `Cache Size: ~691 MB` (`ci-dotnet.yml:53-73`).
`ci-go.yml` sets `cache: false` explicitly in all three jobs; `supply-chain-scan/action.yml:53-57`
repeats the note. Consumers run on persistent self-hosted runners where `~/.nuget/packages` and
`~/go/pkg/mod` are already warm, so there is nothing to gain and a checkout to lose.

---

## 3. Layout

```
.github/workflows/
  pr-check.yml            183 L  THIS repo's gate. Not reusable. Pinned ubuntu-latest.
  security.yml             69 L  sast + supply-chain over our own code (KOR-245).
                                 Thin on purpose: it was copy-pasted into 13 repos and drifted.
  ci-dotnet.yml           254 L  test + coverage. Inlines its own korz-status push (see §5).
  ci-go.yml               162 L  validate + test + coverage + publish-status.
  ci-node.yml             150 L  validate + test + coverage + publish-status.
  build-docker-ecr.yml    155 L  Lambda images. provenance:false (OCI index breaks Lambda).
  deploy-lambda.yml       229 L  deploy-staging + deploy-prod (prod opt-in, off by default).
  publish-ghcr.yml         66 L  ghcr.io/korz-sh/<image>:latest + :v<date>.
  publish-status.yml      193 L  coverage badge -> korz-sh/korz-status. Skips with no token.

.github/actions/
  semgrep-scan/            80 L  p/default + p/secrets (+ optional p/<lang>), --severity ERROR.
  supply-chain-scan/      107 L  trivy fs (vuln,secret,misconfig) + optional .NET lockfile gate.
```

Composite actions, not reusable workflows — see §2. The job-level `container: semgrep/semgrep:1.172.0`
stays in the *caller* (`security.yml:34`) because a composite action cannot declare one.

`ci-*.yml` absorbed the old `{dotnet,go,node}-pr-check.yml` (deleted in `cfd84f5`) and
`deploy-{vercel,web-client}.yml` (deleted in `44de6ed`). Those pr-check files each did their own
checkout, setup and restore, and re-ran the same suite the `test` job already ran — every PR paid
for its test suite twice (`ci-go.yml:15-20`, `ci-node.yml:41-44`, `ci-dotnet.yml:105-109`).

---

## 4. Running it

Nothing here executes locally as a workflow; a reusable workflow is never run in place. What is
runnable is the parse gate.
The manifest entry in `korz-dev/repos.conf` — "sin workflows que parsear" (branch `main`, stack
`yaml`) declares exactly one ci step, and it is the only check that makes sense here:

```bash
cd central-workflows
python3 -c "import glob,sys,yaml; fs=glob.glob('.github/workflows/*.yml'); \
  sys.exit('sin workflows que parsear') if not fs else [yaml.safe_load(open(f)) for f in fs]"
```

Verified 2026-08-23: all 9 workflows parse; every `workflow_call` file declares inputs, so
`pr-check.yml` rule 5 passes. From korz-dev, the same thing via `korz verify central-workflows`.

```bash
# Flip where jobs run, org-wide, with no PR:
gh variable set KORZ_RUNNER_LABELS --org korz-sh --body '["self-hosted","korz-dev"]'
gh variable delete KORZ_RUNNER_LABELS --org korz-sh   # back to hosted
```

```bash
# Read the ruleset. Needs admin:org, which gh's default token lacks:
#   gh auth refresh -h github.com -s admin:org
gh api /orgs/korz-sh/rulesets/20664553
```

---

## 5. Gotchas that have cost time

- **`README.md` is stale in five places.** It documents `dotnet-pr-check.yml`, `go-pr-check.yml`,
  `node-pr-check.yml`, `deploy-web-client.yml` and `deploy-vercel.yml` — **all five are deleted**
  (`cfd84f5`, `44de6ed`). It claims *"11 reusable workflows"*; there are **7** (9 files, minus
  `pr-check.yml` and `security.yml`, which are not `workflow_call`). It documents
  `extra-staging-branch` on `deploy-lambda`, which no longer exists, and shows `secrets: inherit`
  on the `ci-*` examples, which KOR-251 removed from every real caller. **The code wins.**
  `web-client/.github/workflows/deploy-aws.yml:6` still references
  `central-workflows/deploy-web-client.yml` in a comment about a file that is gone.

- **The `|| true` / `|| echo` gate used to be unable to fire; it can now, and proves it every run.**
  The old pattern was anchored to the `run:` line itself, so every real command — which lives inside
  a `run: |` block, on the lines that follow — was invisible to it
  (`pr-check.yml` — "THIS GATE COULD NOT FIRE, AND SAID SO IN GREEN."). Today it greps the whole
  file for `|| true` *and* `|| echo`, and excludes only comments, itself, and the
  default-value command substitution matched by its closing paren
  (`pr-check.yml` — "a command substitution supplying a DEFAULT VALUE, which asserts"). Then it
  plants a swallow inside a `run: |` block and **fails the step if the detector misses it**
  (`pr-check.yml` — "the detector cannot see a planted swallow -- it proves nothing"); a green run
  now prints `no swallowed exit codes, and the detector can still see one`.

- **The four `git tag` / `git push` swallows are gone.** Both call sites became an explicit
  existence check instead of `|| true`: `build-docker-ecr.yml` — "el tag ${TAG} ya existe — no se re-taggea"
  and `deploy-lambda.yml` — "el tag ${TAG}-prod ya existe — no se re-taggea", each behind
  `if git rev-parse -q --verify … else`. What is left in the tree is two `|| echo ""` on the SSM
  lookups (`deploy-lambda.yml:136` and `deploy-lambda.yml:221`) — the legitimate default-value
  idiom, excluded on purpose.

- **`.trivyignore` does not exist in this repo.** `security.yml:53-54` says *"Review on the date in
  this repo's `.trivyignore`"* and `supply-chain-scan/action.yml:91-93` says pre-existing debt is
  declared there with an expiry date. `ls -a` shows `.git/ .github/ README.md` and nothing else.
  The two excluded semgrep rules (`run-shell-injection`, `secrets-inherit` → KOR-251) therefore
  have **no review date recorded anywhere**.

- **`ci-dotnet.yml` does not call `publish-status.yml`.** `ci-go` and `ci-node` do, as a proper
  `needs: coverage` job; `ci-dotnet.yml:207-254` inlines its own `git clone korz-status` + badge
  SVG + push instead, using `secrets.GITHUB_TOKEN` — which **cannot write another repo**. It is
  `continue-on-error: true`, so it fails quietly. Two divergent copies of the badge logic.

- **`ci-dotnet` can emit `percentage=unknown`, and the inline publisher cannot handle it.**
  `ci-dotnet.yml:192-203` deliberately reports `unknown` rather than a fake `0` when the summary is
  missing — that fix exists because the badge read **0% for a service actually at 44.5%** (the path
  defaulted to `coverage/coverage.json`, which reportgenerator never writes; it writes
  `Summary.json`, and the field is `.summary.linecoverage`, not `.total.lines.pct`). But
  `ci-dotnet.yml:231` then runs `echo "unknown >= 80" | bc -l`, and line 225 writes
  `"coverage": unknown` — invalid JSON. Masked by `continue-on-error`.

- **`AWS_ROLE_ARN_PROD` is `required: true` even though prod is opt-in** (`deploy-lambda.yml:78-79`).
  A caller that will never deploy to production still has to pass a prod role ARN; korz-query-api
  does exactly that with `prod-branch: ''`.

- **Deploys ship `:latest`, not the tag the build produced.** `deploy-lambda.yml:112` and `:181`
  build `…/<ecr-repo>:latest`, while `build-docker-ecr.yml` outputs a precise
  `v$(date +'%Y%m%d.%H%M%S')`. Two builds landing close together race.

- **`workflow_dispatch` used to be a button that lies.** `build-docker-ecr.yml:74` guards on
  `push || workflow_dispatch`; the old `== 'push'` alone made every caller's "Run workflow" button
  accept the click and skip the only job. Combined with `paths: src/**` filters in the callers,
  the only way to ship an image was to touch a file under `src/` — hence **48 `chore: trigger
  build` commits across 7 repos in 6 months**.

- **PRs cannot build.** `build-docker-ecr`'s OIDC trust policy
  (`build-docker-ecr.yml` — "repo:korz-sh/*:ref:refs/heads/*", declared in
  `infraestructure/app/stacks/ci-oidc/variables.tf` — "repo:korz-sh/*:ref:refs/heads/*") allows
  branch pushes only, so a `pull_request` run is rejected with
  `Not authorized to perform sts:AssumeRoleWithWebIdentity`. Skipping on PRs is deliberate; the
  permanent red it replaced (KOR-67) trained people to merge with `--admin`, which then masked a
  real failure.

- **`version: latest` on golangci-lint does not mean latest.** On both v3 and v6 of the action it
  resolved to 1.64.8, which is built with Go 1.24 and refuses a newer module:
  `can't load config: the Go language version (go1.24) used to build golangci-lint is lower than
  the targeted Go version (1.25.0)`. `ci-go.yml:77-79` pins the action at **v7** — the first
  release accepting golangci-lint v2 — and the tool at **v2.12.2**.

- **`dotnet tool update -g` is not idempotent either.** `install` fails with
  *"La herramienta … ya está instalada"* (exit 1) on a reused runner, and `update` was observed
  doing the same in CI but not locally. Hence `continue-on-error: true` on
  `ci-dotnet.yml:147-149`, with the honest assertion left to the reportgenerator step below it.

- **`dotnet restore` needs GitHub Packages auth.** Without it, `NU1101` for any repo that does not
  vendor a `.nupkg` — entitlement-api's CI had 0 successes in its last 30 runs.
  `ci-dotnet.yml:83-101` is guarded on `nuget.config` mentioning `nuget.pkg.github.com`, so repos
  that vendor (web-api, rbac-api) are untouched.

- **A `.NET` supply-chain scan with no lockfile passes green covering nothing.** Trivy enumerates
  NuGet by *reading* `packages.lock.json`. `supply-chain-scan` therefore ships an opt-in
  `dotnet-lockfile-check` that counts lockfiles against csproj files and errors:
  `.github/actions/supply-chain-scan/action.yml` — "Missing packages.lock.json ($n of $c)" (KOR-249).

- **Semgrep runs at ERROR severity, not WARNING** (`.github/actions/semgrep-scan/action.yml` — "--severity ERROR"),
  and its output is plain text on purpose (no `--quiet`, no `--json`) so the *"Parsed lines" /
  "Targets scanned"* summary stays visible — a scan that failed to parse half the codebase still
  exits green.

---

## 6. Adding something

- **A new reusable workflow** → it must declare `workflow_call` inputs *or* secrets (rule 5), be
  called from a job and never from a step (rule 3), and must not declare `GITHUB_TOKEN` (rule 4) —
  all three rejections are spelled out in the gate, e.g.
  `pr-check.yml` — "workflow_call with no inputs and no secrets".
  Give it `runs-on: ${{ fromJSON(vars.KORZ_RUNNER_LABELS || '"ubuntu-latest"') }}` and a
  `timeout-minutes` — nothing in this org had one, and a hung job holds a shared self-hosted runner
  for the 6h default.
- **A new composite action** → `.github/actions/<name>/action.yml` with a `runs:` block and
  **`shell: bash` on every `run` step**. Pass inputs through `env:`, never interpolate `${{ }}`
  inside the script: that is the injection pattern semgrep flags
  (`.github/actions/semgrep-scan/action.yml` — "yaml.github-actions.security.run-shell-injection"), and this repo
  must not trip its own gate.
  If the org ruleset requires its check by name, it has to be an action, not a workflow.
- **A new required status context** → the ruleset is org-wide config with no generator in the repo
  any more; edit it via `PUT /orgs/korz-sh/rulesets/20664553` and update korz-dev
  `docs/ruleset-korz-security-gate.md` in the same breath.
- **An optional step** → `continue-on-error: true`, never `|| true` or `|| echo`. The real exit code
  survives and the step shows as failed, so a reader can still tell what happened. The gate catches
  both spellings now and greps the whole file, so `|| true` inside a `run: |` block fails the PR
  (`pr-check.yml` — "Use 'continue-on-error: true' if the step is genuinely optional."). The only
  exception it makes is `VAR=$(cmd || echo "")`.
- **Anything at all** → remember there is no staging. The merge is the release, to 12 repos that
  all pin the default branch — e.g.
  `entitlement-api/.github/workflows/ci.yml` — "korz-sh/central-workflows/.github/workflows/ci-dotnet.yml@main".
