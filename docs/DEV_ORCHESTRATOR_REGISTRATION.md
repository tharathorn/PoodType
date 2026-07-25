# Dev Orchestrator Registration Proposal

Status: **proposal only — not executed**. Registration is an owner/operator CLI
action. It does not install Thai Voice Bridge or configure Windows Startup.

## Proposed project

- Name: `thai-voice-bridge`
- Repository: `C:\Users\thaun\Documents\Playground\thai-voice-bridge`
- Default branch: `master`
- Provider: `cursor_agent`
- Push/deploy/integration/cleanup policies: keep defaults **`never`**
- Registered tests:
  - `pytest_all`: `python -m pytest -q`
  - `compile_check`: `python -m compileall -q src`

Current Dev Orchestrator `project add` has no `--allowed-paths` option and creates
projects with `allowed_paths: ["."]`. Do not edit the runtime DB directly. If a
narrower policy is required, add an operator-supported path configuration
command first. For this standalone repository, `"."` permits only this repo.

## Owner commands (run only after approval)

From `C:\Users\thaun\Documents\Playground\dev-orchestrator`:

```powershell
$env:DEV_ORCHESTRATOR_RUNTIME_ROOT = "$env:LOCALAPPDATA\DevOrchestrator"
$py = ".\.venv\Scripts\python.exe"

& $py -m dev_orchestrator project add `
  --name thai-voice-bridge `
  --path C:\Users\thaun\Documents\Playground\thai-voice-bridge `
  --default-branch master `
  --execution-provider cursor_agent `
  --runtime-root $env:DEV_ORCHESTRATOR_RUNTIME_ROOT

& $py -m dev_orchestrator project disable thai-voice-bridge `
  --runtime-root $env:DEV_ORCHESTRATOR_RUNTIME_ROOT
```

Create a temporary operator-owned JSON file outside the repository:

```json
[
  {"id": "pytest_all", "argv": ["python", "-m", "pytest", "-q"]},
  {"id": "compile_check", "argv": ["python", "-m", "compileall", "-q", "src"]}
]
```

Then configure and verify:

```powershell
& $py -m dev_orchestrator project configure-tests thai-voice-bridge `
  --confirm thai-voice-bridge `
  --tests-file C:\path\to\thai-voice-bridge-tests.json `
  --required-id pytest_all `
  --required-id compile_check `
  --runtime-root $env:DEV_ORCHESTRATOR_RUNTIME_ROOT

& $py -m dev_orchestrator project show thai-voice-bridge `
  --runtime-root $env:DEV_ORCHESTRATOR_RUNTIME_ROOT

& $py -m dev_orchestrator project enable thai-voice-bridge `
  --runtime-root $env:DEV_ORCHESTRATOR_RUNTIME_ROOT
```

After registration, verify through read-only MCP `get_project` and
`get_project_health`. Do not change closeout/integration/deploy policies without
a separate owner decision.
