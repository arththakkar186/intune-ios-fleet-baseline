"""Generate a fictional Intune managed-device export plus an Apple Business Manager device list.

The columns match what scripts/Export-ManagedDevices.ps1 writes from Graph
(/deviceManagement/managedDevices) and an ABM CSV export, so the same report runs on
real data. Nothing here is real: serials, names and users are generated from a seed.

    python3 tools/generate_fleet.py --out data/synthetic --seed 21
"""
from __future__ import annotations

import argparse
import csv
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

AS_OF = datetime(2026, 11, 1, 9, 0)
MODELS = [("iPhone 17", "iPhone"), ("iPhone 16", "iPhone"), ("iPhone 15", "iPhone"), ("iPhone 13", "iPhone"),
          ("iPhone 11", "iPhone"), ("iPhone SE (2nd generation)", "iPhone"), ("iPad (A16)", "iPad"), ("iPad Air (M2)", "iPad")]
OS = ["26.1", "26.0.1", "26.0", "18.7", "18.6.2", "18.5", "17.7.10"]
OS_W = [38, 22, 14, 14, 6, 4, 2]
MIN_OS = (18, 7)   # baseline/compliance-ios.json osMinimumVersion
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Riley", "Casey", "Morgan", "Jamie", "Avery", "Quinn", "Drew", "Rowan"]
LAST = ["Nguyen", "Patel", "Smith", "Garcia", "Kim", "Brown", "Singh", "Martin", "Lopez", "Chen", "Wilson", "Clark"]
DEPTS = ["Field Operations", "Sales", "Finance", "IT", "Facilities", "Customer Service"]


def serial(rnd: random.Random) -> str:
    return "".join(rnd.choice(string.ascii_uppercase.replace("O", "").replace("I", "") + "0123456789") for _ in range(10))


def generate(out: Path, seed: int = 21, n: int = 420) -> None:
    rnd = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    intune, abm = [], []
    for i in range(n):
        model, kind = rnd.choice(MODELS)
        sn = serial(rnd)
        user = f"{rnd.choice(FIRST).lower()}.{rnd.choice(LAST).lower()}{i}@contoso.example"
        purchased = AS_OF - timedelta(days=rnd.randint(20, 5 * 365))
        fate = rnd.random()
        abm.append({"serialNumber": sn, "model": model, "orderNumber": f"PO-{rnd.randint(10000, 99999)}",
                    "purchaseDate": purchased.strftime("%Y-%m-%d"),
                    "mdmServer": "Intune" if fate > 0.03 else "",                   # ~3% never assigned in ABM
                    "status": "Assigned" if fate > 0.03 else "Unassigned"})
        if fate < 0.06:          # in ABM but not (yet) enrolled in Intune
            continue
        os_ = rnd.choices(OS, OS_W)[0]
        last = AS_OF - timedelta(hours=rnd.choice([rnd.randint(1, 72)] * 9 + [rnd.randint(24 * 31, 24 * 120)]))
        jail = rnd.random() < 0.004
        passcode = rnd.random() > 0.01
        mtd = "secured" if rnd.random() > 0.015 else rnd.choice(["medium", "high"])
        reasons = []
        if tuple(int(x) for x in os_.split("."))[:2] < MIN_OS:
            reasons.append("osMinimumVersion")
        if jail:
            reasons.append("securityBlockJailbrokenDevices")
        if not passcode:
            reasons.append("passcodeRequired")
        if mtd in ("medium", "high"):
            reasons.append("deviceThreatProtectionRequiredSecurityLevel")
        state = "noncompliant" if reasons else "compliant"
        if last < AS_OF - timedelta(days=30):
            state = "noncompliant" if reasons else "inGracePeriod" if rnd.random() < 0.1 else state
        intune.append({
            "id": f"{rnd.getrandbits(128):032x}", "deviceName": f"{kind}-{sn[-6:]}", "serialNumber": sn, "model": model,
            "operatingSystem": "iOS" if kind == "iPhone" else "iPadOS", "osVersion": os_,
            "userPrincipalName": user, "department": rnd.choice(DEPTS),
            "managedDeviceOwnerType": "company", "deviceEnrollmentType": "appleBulkWithUser" if rnd.random() > 0.02 else "userEnrollment",
            "isSupervised": "True" if rnd.random() > 0.02 else "False",
            "complianceState": state, "nonCompliantSettings": ";".join(reasons),
            "jailBroken": "True" if jail else "False", "isEncrypted": "True",
            "enrolledDateTime": (purchased + timedelta(days=rnd.randint(1, 10))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lastSyncDateTime": last.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "partnerReportedThreatState": mtd,
        })
    for name, rows in (("managed_devices.csv", intune), ("abm_devices.csv", abm)):
        with (out / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--seed", type=int, default=21)
    a = ap.parse_args()
    generate(Path(a.out), a.seed)
    print(f"wrote {a.out}/managed_devices.csv and abm_devices.csv")
