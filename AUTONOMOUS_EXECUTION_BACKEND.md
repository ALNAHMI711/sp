# Autonomous Execution Backend Contract

This document defines the backend contract for the control plane.

## Backend

Primary coding backend: OpenHands Agent Canvas / Agent Server.

Required capabilities:
- isolated workspace per task
- Git repository access
- command execution
- test execution
- persistent task/conversation state
- scheduled or webhook-triggered automation
- observable success/failure state

## Task lifecycle

DISCOVERED
-> PENDING_APPROVAL
-> APPROVED
-> RUNNING
-> TESTING
-> REVIEW
-> COMPLETED

Failure:
RUNNING/TESTING -> BLOCKED

## Completion definition

A task is not completed because an agent says it is complete.

Completion requires:
1. expected change exists;
2. relevant tests pass;
3. CI passes when configured;
4. no policy violation;
5. working tree/branch state is recorded;
6. PR or commit reference is recorded;
7. audit event is written.

## Sensitive boundary

Trading LIVE activation, withdrawals, secret changes, destructive database/repository actions, and production deployment remain approval-gated.

## Deployment target

Preferred final runtime: secured always-on VM with Docker isolation, firewall, TLS, strong API authentication, and separate GitHub credentials. The phone is not a runtime dependency.

OpenHands documents VM deployment and warns that the agent can execute shell commands and access filesystem/network resources, so the runtime must be treated as a privileged machine.
