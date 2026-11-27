# Operations Runbook

## New starter

1. Assign a device from stock (already in ABM and assigned to Intune).
2. If it was used before, confirm it was wiped (Intune → device → *Wipe* history).
3. The user powers on, signs in with their work account in Setup Assistant, and keeps the device on Wi-Fi until Company Portal shows *Compliant*.
4. Check the record: user affinity set, supervised = yes, compliant.

## Lost or stolen

1. Intune → device → **Lost mode** with a message and phone number (supervised only).
2. **Locate device**. Share the location with security only, never with the user.
3. Not recovered within 24 h, or stolen: **Wipe**. Keep the record in ABM so a recovered device re-enrolls.
4. Revoke the user's sessions in Entra ID and reset the password if the device was unlocked when lost.
5. Close the ticket with the Intune action log attached.

## Leaver

1. On the leaver ticket, **Wipe** (corporate) or **Retire** (BYOD, removes corporate data only).
2. Physically collect the device; it re-enrolls when redeployed.
3. If the device is not returned: lost mode → wipe. Activation Lock stays on, so the device can't be used.

## OS update (each Apple release)

1. Day 0: Ring 0 receives a DDM software update declaration with a 7-day deadline.
2. Day 7: Ring 1 and 2, 14-day deadline.
3. When the new release has been out about 30 days and N-1 has had its final patch, raise `osMinimumVersion` in
   `baseline/compliance-ios.json`, update `SUPPORTED_MAJORS` in `tools/validate.py` each September, and open a pull request.
4. Announce the new minimum 14 days before deploying it.

## Annual renewals

| Item | Where | Note |
|---|---|---|
| Apple MDM push certificate | Intune → Tenant administration → Connectors → Apple MDM push | **Renew** with the same Apple ID. Creating a new certificate forces every device to re-enroll |
| ADE token | ABM → MDM server → download token → Intune → Enrollment program tokens → renew | Keep the same MDM server |
| VPP token | ABM → Preferences → Payments and billing → content token → Intune → Apple VPP tokens | Check that licences synced |

## Monthly

Run the fleet report ([reporting.md](reporting.md)) and work each action list.
