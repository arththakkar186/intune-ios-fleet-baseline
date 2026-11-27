"""Check the iOS baseline JSON against the fleet security standard.

    python3 tools/validate.py            # exit 1 on any finding

The rules are the written standard (docs/security-standard.md) expressed as code,
so a weakening change (shorter passcode, jailbreak allowed, CA left off) fails CI
before anyone deploys it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "baseline"
SUPPORTED_MAJORS = [26, 18]   # Apple-supported major iOS releases, newest first (iOS 18 -> 26 in 2025). Update each September.


def load(name: str) -> dict:
    return json.loads((BASE / name).read_text())


def iso_hours(d: str) -> float:
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", d)
    if not m:
        raise ValueError(f"not an ISO-8601 duration: {d}")
    days, h, mi, s = (int(x or 0) for x in m.groups())
    return days * 24 + h + mi / 60 + s / 3600


def ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def check(base: Path = BASE) -> list[str]:
    global BASE
    BASE = base
    f: list[str] = []
    c, r, a, e = load("compliance-ios.json"), load("restrictions-ios.json"), load("app-protection-ios.json"), load("enrollment-ade.json")
    ca, asg = load("conditional-access.json"), load("assignments.json")

    # ---- compliance
    if not c["passcodeRequired"] or c["passcodeMinimumLength"] < 6:
        f.append("compliance: passcode required with at least 6 digits")
    if not c["passcodeBlockSimple"]:
        f.append("compliance: simple passcodes (1234, 1111) must be blocked")
    if c["passcodeMinutesOfInactivityBeforeLock"] is None or c["passcodeMinutesOfInactivityBeforeLock"] > 5:
        f.append("compliance: auto-lock 5 minutes or less")
    if not c["securityBlockJailbrokenDevices"]:
        f.append("compliance: jailbroken devices must be non-compliant")
    n_minus_1 = SUPPORTED_MAJORS[1]
    if ver(c["osMinimumVersion"])[0] < n_minus_1:
        f.append(f"compliance: minimum OS {c['osMinimumVersion']} is older than N-1 (iOS {n_minus_1})")
    if ver(a["minimumRequiredOsVersion"]) > ver(c["osMinimumVersion"]):
        f.append("app protection: minimum OS must not be stricter than device compliance (BYOD would be blocked first)")
    if not c["deviceThreatProtectionEnabled"]:
        f.append("compliance: mobile threat defense signal must be required")
    blocks = [x for rule in c["scheduledActionsForRule"] for x in rule["scheduledActionConfigurations"] if x["actionType"] == "block"]
    if not blocks or blocks[0]["gracePeriodHours"] > 72:
        f.append("compliance: mark non-compliant (block) within 72 hours")

    # ---- restrictions (supervised)
    for k in ("iCloudBlockBackup", "iCloudBlockDocumentSync", "documentsBlockManagedDocumentsInUnmanagedApps",
              "enterpriseAppBlockTrust", "configurationProfileBlockChanges", "hostPairingBlocked"):
        if not r.get(k):
            f.append(f"restrictions: {k} must be true")
    if r["passcodeSignInFailureCountBeforeWipe"] > 10:
        f.append("restrictions: wipe after 10 or fewer failed passcode attempts")

    # ---- app protection
    if a["allowedOutboundDataTransferDestinations"] != "managedApps" or a["allowedInboundDataTransferSources"] != "managedApps":
        f.append("app protection: data transfer limited to managed apps")
    if a["allowedOutboundClipboardSharingLevel"] not in ("managedApps", "managedAppsWithPasteIn", "blocked"):
        f.append("app protection: clipboard out of managed apps must be blocked")
    if not a["dataBackupBlocked"] or not a["saveAsBlocked"]:
        f.append("app protection: backup and Save As to personal locations must be blocked")
    if not a["pinRequired"] or a["minimumPinLength"] < 6:
        f.append("app protection: app PIN of 6+ digits")
    if iso_hours(a["periodOfflineBeforeWipeIsEnforced"]) > 90 * 24:
        f.append("app protection: selective wipe after 90 days offline or less")
    if iso_hours(a["periodOfflineBeforeAccessCheck"]) > 24:
        f.append("app protection: re-check access at least every 24 hours offline")
    if a["managedBrowser"] != "microsoftEdge" or not a["managedBrowserToOpenLinksRequired"]:
        f.append("app protection: corporate links open in Edge")
    if "com.microsoft.Office.Outlook" not in a["apps"]:
        f.append("app protection: Outlook must be targeted")

    # ---- enrollment
    for k in ("supervisedModeEnabled", "isMandatory", "profileRemovalDisabled", "requiresUserAuthentication", "awaitDeviceConfiguredConfirmation"):
        if not e.get(k):
            f.append(f"enrollment: {k} must be true")
    if not e.get("restoreBlocked"):
        f.append("enrollment: restore from personal backup must be blocked")

    # ---- conditional access
    grants = {g for p in ca["policies"] for g in p["grantControls"]["builtInControls"]}
    if not {"compliantDevice", "compliantApplication"} <= grants:
        f.append("conditional access: needs both a compliant-device and an app-protection policy")
    for p in ca["policies"]:
        if "CA-Exclude-BreakGlass" not in p["conditions"]["users"].get("excludeGroups", []):
            f.append(f"conditional access: '{p['displayName']}' must exclude break-glass accounts")
        if p["state"] not in ("enabledForReportingButNotEnforced", "enabled"):
            f.append(f"conditional access: '{p['displayName']}' state {p['state']} is not allowed")

    # ---- assignments
    groups = set(asg["groups"])
    for obj, targets in asg["assignments"].items():
        if not (BASE / obj).exists():
            f.append(f"assignments: {obj} does not exist")
        for t in targets:
            if t not in groups:
                f.append(f"assignments: {obj} -> unknown group '{t}'")
    for ring in asg["rings"]:
        if ring["group"] not in groups:
            f.append(f"rings: unknown group '{ring['group']}'")
    if e["displayName"] not in asg["groups"]["IOS-Corporate-Devices"]["rule"]:
        f.append("assignments: IOS-Corporate-Devices rule must match the ADE profile name")
    return f


def main() -> int:
    findings = check()
    for x in findings:
        print(f"FAIL  {x}")
    if not findings:
        print("iOS baseline meets the fleet security standard.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
