"""Fleet health report: compliance, OS currency, stale devices, ABM-to-Intune reconciliation, refresh candidates.

    python3 tools/fleet_report.py --data data/synthetic --out out --as-of 2026-11-01

Inputs  managed_devices.csv  (scripts/Export-ManagedDevices.ps1)
        abm_devices.csv      (Apple Business Manager > Devices > export)
Outputs out/fleet_report.md and action lists (CSV) for each finding.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

STALE_DAYS = 30
# Hardware generations that will not receive the next major iOS release. Example list; maintain each September.
END_OF_SUPPORT_SOON = {"iPhone 11", "iPhone SE (2nd generation)"}   # oldest A13 models in this fleet


def read(path: Path) -> list[dict]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def analyse(devices: list[dict], abm: list[dict], as_of: datetime, min_os: str) -> dict:
    stale_cut = as_of - timedelta(days=STALE_DAYS)
    by_serial = {d["serialNumber"]: d for d in devices}
    abm_serials = {a["serialNumber"] for a in abm}

    state = Counter(d["complianceState"] for d in devices)
    reasons = Counter(r for d in devices for r in d["nonCompliantSettings"].split(";") if r)
    os_major = Counter(d["osVersion"].split(".")[0] for d in devices)
    below_min = [d for d in devices if ver(d["osVersion"]) < ver(min_os)]
    stale = [d for d in devices if ts(d["lastSyncDateTime"]) < stale_cut]
    not_supervised = [d for d in devices if d["isSupervised"] != "True"]
    not_ade = [d for d in devices if d["deviceEnrollmentType"] != "appleBulkWithUser"]
    abm_unassigned = [a for a in abm if a["status"] != "Assigned"]
    abm_not_enrolled = [a for a in abm if a["status"] == "Assigned" and a["serialNumber"] not in by_serial]
    intune_not_in_abm = [d for d in devices if d["serialNumber"] not in abm_serials]
    jailbroken = [d for d in devices if d["jailBroken"] == "True"]
    refresh = [d for d in devices if d["model"] in END_OF_SUPPORT_SOON]

    return {
        "as_of": as_of.strftime("%Y-%m-%d"), "devices": len(devices), "abm_devices": len(abm),
        "compliance": dict(state), "compliance_pct": round(100 * state.get("compliant", 0) / len(devices), 1),
        "noncompliance_reasons": dict(reasons.most_common()), "os_major": dict(sorted(os_major.items(), reverse=True)),
        "lists": {"below_min_os": below_min, "stale": stale, "not_supervised": not_supervised, "not_ade": not_ade,
                  "abm_unassigned": abm_unassigned, "abm_not_enrolled": abm_not_enrolled,
                  "intune_not_in_abm": intune_not_in_abm, "jailbroken": jailbroken, "refresh_candidates": refresh},
    }


ACTIONS = {
    "jailbroken": "Retire immediately; investigate with security",
    "below_min_os": "Notify user; force update with a DDM software update declaration; blocked by CA until updated",
    "stale": f"No check-in for {STALE_DAYS}+ days: contact user, then lost-device process (lock / locate / wipe)",
    "not_supervised": "Re-enroll through ADE (supervised) at next service visit",
    "not_ade": "Corporate device enrolled outside ADE: re-enroll so it cannot remove management",
    "abm_unassigned": "Assign to the Intune MDM server in ABM",
    "abm_not_enrolled": "Assigned in ABM but never enrolled: locate device (stock, lost, or awaiting deployment)",
    "intune_not_in_abm": "Corporate device not in ABM: add with Apple Configurator, or reclassify as personal",
    "refresh_candidates": "Plan replacement before the hardware loses major-OS support",
}


def render(r: dict) -> str:
    L = [f"# iOS fleet report ({r['as_of']})", "",
         f"Intune devices: **{r['devices']}** · ABM devices: **{r['abm_devices']}** · compliant: **{r['compliance_pct']}%**", "",
         "## Compliance", "", "| State | Devices |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in sorted(r["compliance"].items(), key=lambda x: -x[1])]
    L += ["", "| Non-compliance reason | Devices |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in r["noncompliance_reasons"].items()]
    L += ["", "## OS currency", "", "| iOS major | Devices |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in r["os_major"].items()]
    L += ["", "## Action lists", "", "| Finding | Devices | Action | File |", "|---|---:|---|---|"]
    for k, rows in r["lists"].items():
        L.append(f"| {k.replace('_', ' ')} | {len(rows)} | {ACTIONS[k]} | `{k}.csv` |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--out", default="out")
    ap.add_argument("--as-of", default="2026-11-01")
    ap.add_argument("--min-os", default=None, help="default: osMinimumVersion from baseline/compliance-ios.json")
    a = ap.parse_args(argv)
    base = Path(__file__).resolve().parent.parent / "baseline" / "compliance-ios.json"
    min_os = a.min_os or json.loads(base.read_text())["osMinimumVersion"]
    data, out = Path(a.data), Path(a.out)
    r = analyse(read(data / "managed_devices.csv"), read(data / "abm_devices.csv"), datetime.strptime(a.as_of, "%Y-%m-%d"), min_os)
    out.mkdir(parents=True, exist_ok=True)
    for k, rows in r["lists"].items():
        with (out / f"{k}.csv").open("w", newline="") as fh:
            if rows:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    (out / "fleet_report.md").write_text(render(r))
    print(f"{r['devices']} devices, {r['compliance_pct']}% compliant; " +
          ", ".join(f"{k} {len(v)}" for k, v in r["lists"].items()) + f". Report: {out}/fleet_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
