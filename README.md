# Central Workflows

Reusable GitHub Actions workflows for Korz services.

## Workflows

### `publish-status`

Publishes code coverage metrics to [korz-status](https://github.com/korz-sh/korz-status) dashboard.

**Usage:**

```yaml
# In your service repository (.github/workflows/ci.yml)

- name: Publish Coverage
  uses: korz-sh/central-workflows/.github/workflows/publish-status.yml@main
  with:
    service-name: entitlement-api
    coverage-percentage: 75.5
    run-id: ${{ github.run_id }}
  secrets:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Inputs:**
- `service-name` (required): Service name (e.g., `entitlement-api`)
- `coverage-percentage` (required): Coverage percentage (e.g., `75.5`)
- `run-id` (optional): Source workflow run ID

**Secrets:**
- `GITHUB_TOKEN`: GitHub token with write access to korz-status

---

## Architecture

```
┌─ Each Service Repo ──────────────────┐
│ (.github/workflows/ci.yml)           │
│                                      │
│ 1. Run tests & generate coverage     │
│ 2. Call publish-status workflow      │
│    └─ Service name + coverage %      │
└──────────────┬──────────────────────┘
               │
               ↓
┌─ Central Workflows ──────────────────┐
│ (this repo)                          │
│                                      │
│ publish-status.yml                   │
│ ├─ Receives: service, coverage       │
│ ├─ Generates: badge SVG              │
│ ├─ Creates: JSON report              │
│ └─ Pushes: to korz-status            │
└──────────────┬──────────────────────┘
               │
               ↓
┌─ korz-status (Public Dashboard) ──────┐
│ (korz-sh/korz-status)                 │
│                                       │
│ ├─ README with coverage table         │
│ ├─ .badges/ directory (SVG badges)    │
│ ├─ reports/ directory (JSON data)     │
│ └─ coverage/ directory (HTML reports) │
└────────────────────────────────────────┘
```

---

## Setup

### In each service repository:

1. **Add to `.github/workflows/ci.yml`** (after tests pass):

```yaml
- name: Extract coverage
  id: coverage
  run: |
    # C#: Extract from coverage report
    COVERAGE=$(jq '.total.lines.pct' coverage/coverage-summary.json)
    echo "percentage=$COVERAGE" >> $GITHUB_OUTPUT

- name: Publish to korz-status
  if: success()
  uses: korz-sh/central-workflows/.github/workflows/publish-status.yml@main
  with:
    service-name: ${{ github.event.repository.name }}
    coverage-percentage: ${{ steps.coverage.outputs.percentage }}
    run-id: ${{ github.run_id }}
  secrets:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

2. **Verify workflow permissions:**

Repository → Settings → Actions → General → Workflow permissions
- ✅ Read and write permissions
- ✅ Allow GitHub Actions to create and approve pull requests

---

## Status

- ✅ `publish-status.yml` - Publish coverage to korz-status
- 🔄 Additional workflows coming soon

---

**Last updated**: 2026-05-31
