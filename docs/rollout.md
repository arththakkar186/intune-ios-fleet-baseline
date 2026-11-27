# Rollout Plan

| Ring | Group | Size | Soak | Exit criteria |
|---|---|---|---:|---|
| 0 IT pilot | `IOS-Pilot-Devices` | ~2% | 7 days | All pilot devices check in and are compliant; no blocking tickets; app installs succeed |
| 1 Early adopters | `IOS-Ring1-Devices` | ~10% across departments | 7 days | Compliance ≥ 95%; ticket rate not higher than baseline; field-worker apps tested |
| 2 Broad | `IOS-Corporate-Devices` | rest | n/a | Compliance ≥ 95% after 14 days |

## Conditional Access cut-over

1. Deploy both CA policies in **report-only** (default for `Deploy-IntuneBaseline.ps1`).
2. Run for at least 7 days. In Entra sign-in logs, filter *Conditional Access: report-only failure* for the two policies.
3. Contact everyone who would be blocked. Usually the fix is an OS update or opening Company Portal.
4. When report-only failures are only stale or test accounts, run `-EnableConditionalAccess`.
5. Watch the service desk queue for 48 h.

## Communication

- 2 weeks before: what changes, why, and what the user must do (update iOS, install Company Portal).
- Release day: short how-to with screenshots of the "your device needs attention" message.
- Service desk script: check compliance in Company Portal → *Check status* → follow the reason.

## Rollback

| Problem | Action |
|---|---|
| Users blocked unexpectedly | Set the CA policy back to report-only (`Deploy-IntuneBaseline.ps1` without `-EnableConditionalAccess`) |
| A restriction breaks a business app | Revert the commit, redeploy the ring; affected devices receive the previous profile at next check-in |
| Compliance setting too strict | Revert; devices re-evaluate within ~8 h, or immediately with *Check status* |
