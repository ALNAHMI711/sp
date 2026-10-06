# Autonomous Cloud Execution & Control Hub

## Purpose
`sp` is the control hub for an autonomous coding worker. The phone is only a control/monitoring client; the worker runs independently in cloud infrastructure.

## Initial repositories
- ALNAHMI711/Ahmed-Alnahmi-711 — trading execution foundation
- ALNAHMI711/autonomous-business-manager — automation/orchestration
- ALNAHMI711/- — content automation
- ALNAHMI711/tte — trading/chart terminal

## Safe lifecycle
DISCOVERED -> INSPECTING -> TESTING -> PROPOSED -> CI -> READY

Failures return to TESTING or PROPOSED; sensitive actions require explicit approval.

## Hard safety boundary
The worker must never autonomously:
- enable Binance LIVE trading;
- enable withdrawals;
- rotate or expose secrets;
- deploy destructive production changes;
- liquidate positions as a generic recovery action.

Risk controls cannot be bypassed by AI, strategy, Telegram, or automation.

## Bootstrap mode
The initial GitHub Actions worker is intentionally read-only. It establishes the control point and safety boundary before a write-capable worker is introduced.

## Future worker
A later worker may create branches, edit files, run tests, create PRs, and monitor CI. Write access should remain scoped to repository contents and pull requests, with sensitive operations separated behind explicit approval.

## Phone independence
Closing the phone or losing mobile connectivity must not stop cloud execution. The phone only sends commands and reads status.
