from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fleet_report  # noqa: E402
import generate_fleet  # noqa: E402
import validate  # noqa: E402


class Baseline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        for p in (ROOT / "baseline").glob("*.json"):
            shutil.copy(p, self.base / p.name)

    def tearDown(self):
        self.tmp.cleanup()

    def mutate(self, name, **changes):
        p = self.base / name
        d = json.loads(p.read_text())
        for k, v in changes.items():
            d[k] = v
        p.write_text(json.dumps(d))
        return validate.check(self.base)

    def test_committed_baseline_is_clean(self):
        self.assertEqual(validate.check(ROOT / "baseline"), [])

    def test_weakening_changes_fail(self):
        cases = [
            ("compliance-ios.json", {"passcodeMinimumLength": 4}, "6 digits"),
            ("compliance-ios.json", {"securityBlockJailbrokenDevices": False}, "jailbroken"),
            ("compliance-ios.json", {"osMinimumVersion": "17.7"}, "older than N-1"),
            ("compliance-ios.json", {"passcodeMinutesOfInactivityBeforeLock": 15}, "auto-lock"),
            ("restrictions-ios.json", {"iCloudBlockBackup": False}, "iCloudBlockBackup"),
            ("restrictions-ios.json", {"enterpriseAppBlockTrust": False}, "enterpriseAppBlockTrust"),
            ("app-protection-ios.json", {"allowedOutboundDataTransferDestinations": "allApps"}, "managed apps"),
            ("app-protection-ios.json", {"periodOfflineBeforeWipeIsEnforced": "P180D"}, "90 days"),
            ("app-protection-ios.json", {"minimumRequiredOsVersion": "26.0"}, "stricter than device compliance"),
            ("app-protection-ios.json", {"saveAsBlocked": False}, "Save As"),
            ("enrollment-ade.json", {"profileRemovalDisabled": False}, "profileRemovalDisabled"),
            ("enrollment-ade.json", {"supervisedModeEnabled": False}, "supervisedModeEnabled"),
        ]
        for name, change, expect in cases:
            with self.subTest(name=name, change=change):
                self.tearDown()
                self.setUp()
                findings = self.mutate(name, **change)
                self.assertTrue(any(expect in f for f in findings), findings)

    def test_conditional_access_must_exclude_break_glass(self):
        p = self.base / "conditional-access.json"
        d = json.loads(p.read_text())
        d["policies"][0]["conditions"]["users"]["excludeGroups"] = []
        d["policies"][1]["state"] = "disabled"
        p.write_text(json.dumps(d))
        f = validate.check(self.base)
        self.assertTrue(any("break-glass" in x for x in f))
        self.assertTrue(any("state disabled" in x for x in f))

    def test_dynamic_group_matches_enrollment_profile(self):
        f = self.mutate("enrollment-ade.json", displayName="Renamed profile")
        self.assertTrue(any("ADE profile name" in x for x in f))

    def test_iso_durations(self):
        self.assertEqual(validate.iso_hours("PT30M"), 0.5)
        self.assertEqual(validate.iso_hours("P90D"), 2160)
        self.assertEqual(validate.iso_hours("PT12H"), 12)


class FleetReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "d"
        generate_fleet.generate(cls.data, seed=21)
        read = fleet_report.read
        cls.devices, cls.abm = read(cls.data / "managed_devices.csv"), read(cls.data / "abm_devices.csv")
        cls.r = fleet_report.analyse(cls.devices, cls.abm, datetime(2026, 11, 1), "18.7")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_generator_is_deterministic_and_matches_committed_data(self):
        for name in ("managed_devices.csv", "abm_devices.csv"):
            self.assertEqual((self.data / name).read_text(), (ROOT / "data" / "synthetic" / name).read_text())

    def test_version_compare_is_numeric(self):
        self.assertLess(fleet_report.ver("18.6.2"), fleet_report.ver("18.7"))
        self.assertLess(fleet_report.ver("18.7"), fleet_report.ver("26.0"))
        self.assertGreater(fleet_report.ver("18.10"), fleet_report.ver("18.7"))

    def test_below_min_matches_compliance_reason(self):
        flagged = {d["serialNumber"] for d in self.r["lists"]["below_min_os"]}
        reason = {d["serialNumber"] for d in self.devices if "osMinimumVersion" in d["nonCompliantSettings"]}
        self.assertEqual(flagged, reason)

    def test_abm_reconciliation_partitions_population(self):
        enrolled = {d["serialNumber"] for d in self.devices}
        l = self.r["lists"]
        accounted = len(enrolled & {a["serialNumber"] for a in self.abm}) + len(l["abm_not_enrolled"]) + \
            len([a for a in l["abm_unassigned"] if a["serialNumber"] not in enrolled])
        self.assertEqual(accounted, len(self.abm))

    def test_jailbroken_devices_are_noncompliant(self):
        for d in self.r["lists"]["jailbroken"]:
            self.assertEqual(d["complianceState"], "noncompliant")

    def test_no_real_identities(self):
        upns = {d["userPrincipalName"].split("@")[1] for d in self.devices}
        self.assertEqual(upns, {"contoso.example"})

    def test_cli_writes_report_and_lists(self):
        out = Path(self.tmp.name) / "out"
        fleet_report.main(["--data", str(self.data), "--out", str(out)])
        self.assertIn("compliant", (out / "fleet_report.md").read_text())
        with (out / "stale.csv").open() as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), len(self.r["lists"]["stale"]))


if __name__ == "__main__":
    unittest.main()
