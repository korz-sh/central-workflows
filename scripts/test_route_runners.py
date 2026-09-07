import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("routing", Path(__file__).with_name("route-runners.py"))
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


def test_native_security_and_utility_keep_fallbacks_and_checks():
    text = """jobs:
  sast:
    runs-on: ${{ vars.KORZ_CODEBUILD_PROJECT || 'ubuntu-latest' }}
    container: semgrep/semgrep:1.172.0
    steps:
      - uses: korz-sh/central-workflows/.github/actions/semgrep-scan@main
        with:
          lang: python
  gate:
    needs: [sast, supply-chain]
    if: always()
    runs-on: ${{ fromJSON(vars.KORZ_RUNNER_LABELS || '"ubuntu-latest"') }}
"""
    changed = routing.transform(text)
    assert "container:" not in changed
    assert "KORZ_SECURITY_RUNNER_LABELS" in changed
    assert "KORZ_UTILITY_RUNNER_LABELS" in changed
    assert "KORZ_CODEBUILD_PROJECT" in changed
    assert "lang: python" in changed
    assert "needs: [sast, supply-chain]" in changed
    assert routing.transform(changed) == changed


def test_architecture_specific_and_pinned_runners_are_unchanged():
    text = """jobs:
  build:
    runs-on: ${{ vars.ARM_RUNNER || 'ubuntu-24.04-arm' }}
  validate:
    runs-on: ubuntu-latest
"""
    assert routing.transform(text) == text
