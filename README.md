# Central Workflows

Reusable GitHub Actions workflows for all Korz services. Each service repo calls these via `workflow_call` — no duplicated pipeline logic.

## Workflows

### Build & Publish

#### `build-docker-ecr.yml` — Build and push to Amazon ECR

For Lambda container images. Enforces `provenance: false` (required for Lambda — OCI index breaks function updates).

```yaml
jobs:
  build:
    uses: korz-sh/central-workflows/.github/workflows/build-docker-ecr.yml@main
    with:
      ecr-repo: my-service           # required — explicit, no derivation
      dockerfile: Dockerfile.lambda  # optional, default: Dockerfile.lambda
      aws-region: us-east-2          # optional, default: us-east-2
      pass-github-token-build-arg: true  # optional, default: true
    secrets:
      AWS_ROLE_ARN_STAGING: ${{ secrets.AWS_ROLE_ARN_STAGING }}
      GH_PAT: ${{ secrets.GH_PAT }}  # optional
```

**Outputs:** `image-uri`, `image-tag`

---

#### `publish-ghcr.yml` — Build and push to GitHub Container Registry

```yaml
jobs:
  publish:
    uses: korz-sh/central-workflows/.github/workflows/publish-ghcr.yml@main
    with:
      image-name: my-service   # required
      build-args: |            # optional, newline-separated
        NPM_TOKEN=${{ secrets.NPM_TOKEN }}
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

**Outputs:** `image-tag`

---

### CI (validate → test → coverage → korz-status)

#### `ci-dotnet.yml`

```yaml
jobs:
  ci:
    uses: korz-sh/central-workflows/.github/workflows/ci-dotnet.yml@main
    with:
      service-name: my-service          # required
      dotnet-version: '10.0.x'          # optional, default: 10.0.x
      coverage-json-path: 'coverage/coverage.json'  # optional
    secrets: inherit
```

#### `ci-go.yml`

```yaml
jobs:
  ci:
    uses: korz-sh/central-workflows/.github/workflows/ci-go.yml@main
    with:
      service-name: my-service   # required
      go-version: '1.23.x'       # optional, default: 1.23.x
    secrets: inherit
```

#### `ci-node.yml`

```yaml
jobs:
  ci:
    uses: korz-sh/central-workflows/.github/workflows/ci-node.yml@main
    with:
      service-name: my-service          # required
      node-version: '20.x'              # optional, default: 20.x
      package-manager: npm              # optional: npm | pnpm, default: npm
      pnpm-version: '9.1.4'             # optional
      coverage-glob: 'src/**/*.ts'      # optional
      run-type-check: false             # optional, default: false
    secrets: inherit
```

---

### PR Checks

#### `dotnet-pr-check.yml`

```yaml
jobs:
  pr-check:
    uses: korz-sh/central-workflows/.github/workflows/dotnet-pr-check.yml@main
    with:
      dotnet-version: '10.0'   # optional, default: 10.0
```

#### `go-pr-check.yml`

```yaml
jobs:
  pr-check:
    uses: korz-sh/central-workflows/.github/workflows/go-pr-check.yml@main
    with:
      go-version: '1.22'   # optional, default: 1.22
```

**Jobs:** `test` (with Codecov), `build` (CGO_ENABLED=0 GOOS=linux GOARCH=amd64), `lint` (golangci-lint)

#### `node-pr-check.yml`

```yaml
jobs:
  pr-check:
    uses: korz-sh/central-workflows/.github/workflows/node-pr-check.yml@main
    with:
      node-version: '20'           # optional, default: 20
      package-manager: pnpm        # optional: npm | pnpm, default: npm
      pnpm-version: '9.1.4'        # optional
      codecov-flag: my-service     # optional
      run-e2e: true                # optional, default: false — enables Playwright job
```

---

### Deploy

#### `deploy-lambda.yml` — Deploy ECR image to AWS Lambda

Triggered via `workflow_run`. Caller passes event context as inputs.

```yaml
# In your service repo:
on:
  workflow_run:
    workflows: ['Build']
    branches: [develop, main]
    types: [completed]

jobs:
  deploy:
    uses: korz-sh/central-workflows/.github/workflows/deploy-lambda.yml@main
    with:
      ecr-repo: my-service                                          # required
      build-conclusion: ${{ github.event.workflow_run.conclusion }} # required
      trigger-branch: ${{ github.event.workflow_run.head_branch }}  # required
      staging-branch: develop           # optional, default: develop
      extra-staging-branch: master      # optional — second branch for staging
      aws-region-staging: us-east-2     # optional
      aws-region-prod: us-east-1        # optional
      create-release-tag: false         # optional — git tag on prod deploy
    secrets:
      AWS_ROLE_ARN_STAGING: ${{ secrets.AWS_ROLE_ARN_STAGING }}
      AWS_ROLE_ARN_PROD: ${{ secrets.AWS_ROLE_ARN_PROD }}
```

Lambda function names are read from repository variables `LAMBDA_FUNCTION_STAGING` and `LAMBDA_FUNCTION_PROD`.

#### `deploy-web-client.yml` — Inline build + SSM tag promotion

For services with a unique deploy strategy: builds and pushes the image inline (no separate build.yml), stores the tag in SSM on staging, then promotes it to prod.

```yaml
on:
  push:
    branches: [develop, main]

jobs:
  deploy:
    uses: korz-sh/central-workflows/.github/workflows/deploy-web-client.yml@main
    with:
      ecr-repository: korz/web-client              # required
      ssm-tag-param: /korz/web-client/latest-dev-tag  # optional
      aws-region: us-east-1                         # optional
    secrets:
      AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}
```

---

#### `publish-status.yml` — Publish coverage to korz-status dashboard

Called internally by `ci-dotnet.yml`, `ci-go.yml`, and `ci-node.yml`. Pushes coverage percentage and badge to [korz-status](https://github.com/korz-sh/korz-status).

```yaml
uses: korz-sh/central-workflows/.github/workflows/publish-status.yml@main
with:
  service-name: my-service
  coverage-percentage: ${{ steps.coverage.outputs.percentage }}
  run-id: ${{ github.run_id }}
secrets:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Architecture

```
┌─ Each Service Repo ─────────────────────────────┐
│  .github/workflows/                             │
│  ├── build.yml      → build-docker-ecr.yml      │
│  ├── publish.yml    → publish-ghcr.yml          │
│  ├── ci.yml         → ci-{dotnet|go|node}.yml   │
│  ├── pr-check.yml   → {dotnet|go|node}-pr-check │
│  └── deploy.yml     → deploy-lambda.yml         │
└─────────────────────┬───────────────────────────┘
                      │ workflow_call
                      ↓
┌─ central-workflows (this repo) ─────────────────┐
│  11 reusable workflows                          │
│  Single source of truth for all pipeline logic  │
└─────────────────────┬───────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ↓           ↓           ↓
        ECR         GHCR     korz-status
```

## What stays local per service

Triggers (`on: push/pull_request` with `paths:` and `branches:`) cannot be passed into `workflow_call` — each service keeps its own trigger block. Everything else lives here.

## Services using these workflows

| Service | build | publish | ci | pr-check | deploy |
|---|---|---|---|---|---|
| entitlement-api | ECR (.NET) | GHCR | dotnet | dotnet | lambda |
| identity-api-v2 | ECR (Go) | GHCR | go | go | lambda |
| payments-service-api | ECR (Node) | GHCR | node | node | lambda |
| rbac-api | ECR (.NET) | — | dotnet | dotnet | lambda |
| web-api | ECR (.NET) | GHCR | dotnet | dotnet | lambda |
| web-client | — | GHCR | node | node | web-client |
