# Fleet Reporting

```bash
pwsh ./scripts/Export-ManagedDevices.ps1 -OutFile ./data/live/managed_devices.csv   # read-only Graph
# ABM > Devices > export CSV  ->  ./data/live/abm_devices.csv
python3 tools/fleet_report.py --data ./data/live --out ./out/$(date +%Y-%m)
```

Do not commit `data/live/`. It contains real serials and user names.

## Findings, thresholds and actions

| Finding | Definition | Target | Action |
|---|---|---|---|
| Compliance % | `complianceState = compliant` / all iOS devices | ≥ 95% | Work the reason table, largest first |
| Below minimum OS | `osVersion` < baseline `osMinimumVersion` (numeric compare) | 0 after the 14-day notice | DDM update with deadline; CA blocks until updated |
| Stale | No check-in for 30+ days | < 2% | Contact user → lost-device process |
| Not supervised | `isSupervised = False` on a corporate device | 0 | Re-enroll through ADE |
| Not ADE | Corporate device enrolled another way | 0 | Re-enroll through ADE |
| ABM unassigned | Device in ABM without an MDM server | 0 | Assign to Intune |
| ABM assigned, not enrolled | In ABM and assigned, but not in Intune | Explainable (stock) | Match against stock list; otherwise locate |
| Intune not in ABM | Corporate device missing from ABM | 0 | Add with Apple Configurator or reclassify |
| Jailbroken | `jailBroken = True` | 0 | Retire immediately; security investigation |
| Refresh candidates | Models expected to lose major-OS support next | Plan | Budget and replace before support ends |

## Example output (synthetic data)

| Finding | Devices |
|---|---:|
| Intune devices / ABM devices | 400 / 420 |
| Compliant | 84.5% |
| Below minimum OS (18.7) | 48 |
| Stale (30+ days) | 35 |
| Not supervised / not ADE | 7 / 6 |
| ABM unassigned / assigned but not enrolled | 11 / 9 |
| Jailbroken | 2 |
| Refresh candidates | 103 |

These numbers come from the seeded generator. They show what the report produces and do not describe any real fleet.
