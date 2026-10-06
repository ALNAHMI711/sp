# OpenHands backend integration status

Status: READY_FOR_RUNTIME_BINDING

## Selected upstream

Use the current `OpenHands/OpenHands` repository and Agent Canvas. The old `OpenHands/agent-canvas` repository is archived and must not be used as the integration target.

## What sp owns

- approved repository registry
- task policy
- approval gates
- sensitive-operation deny rules
- project lifecycle state
- audit records
- completion verification
- notifications

## What OpenHands owns

- agent conversations
- workspace/tool execution
- coding-agent runtime
- model/agent backend selection
- automation scheduling and webhook dispatch
- execution history

## What GitHub owns

- repository source
- branches
- pull requests
- Actions/CI
- final merge controls

## Runtime requirement

A production deployment needs an always-on VM or equivalent. GitHub Actions remains useful for CI but is not the permanent agent host.

## Next implementation step

Bind an OpenHands Agent Server URL and API key through runtime secrets, then create one non-sensitive smoke-test automation against a selected repository. Do not put the API key or GitHub credentials in source control.
