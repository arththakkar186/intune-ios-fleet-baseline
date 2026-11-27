# iOS / iPadOS Security Standard

Requirements for corporate-owned iPhones and iPads, and for Microsoft 365 data on any iOS device. Each line is
checked by `tools/validate.py`.

## 1. Enrollment (corporate devices)

| # | Requirement | Reason |
|---|---|---|
| 1.1 | Every corporate device is in Apple Business Manager and enrolls through ADE | A device can't be bought around management, and it re-enrolls automatically after a wipe |
| 1.2 | Supervised, management mandatory, profile cannot be removed | The user cannot remove management, and supervision unlocks the stronger restrictions |
| 1.3 | User signs in with Entra ID during Setup Assistant | Device gets user affinity, so compliance and CA apply to the right person |
| 1.4 | Restore from a personal backup is blocked | Prevents personal data and profiles from coming onto the corporate device |

## 2. Device compliance

| # | Requirement | Reason |
|---|---|---|
| 2.1 | Passcode required, at least 6 digits, simple codes blocked | Protects the data-protection keys; 4-digit codes are guessable |
| 2.2 | Auto-lock 5 minutes or less | Limits exposure of an unattended device |
| 2.3 | OS no older than the latest release of the previous major (N-1); currently **18.7** | Unpatched iOS releases are actively exploited; N-1 gives users time to update without losing support |
| 2.4 | Jailbroken devices are non-compliant | A jailbreak removes the sandbox that every other control depends on |
| 2.5 | Mobile threat defense risk medium or lower | Catches malicious profiles, risky networks and phishing apps |
| 2.6 | Non-compliant devices are blocked after a 24 h grace period (72 h maximum) | Time to fix without the user losing email in the middle of the day |

## 3. Device restrictions (supervised)

| # | Requirement |
|---|---|
| 3.1 | No iCloud backup or iCloud document sync, and no managed app sync to iCloud |
| 3.2 | Managed documents cannot be opened in unmanaged apps |
| 3.3 | Untrusted enterprise (sideloaded) apps blocked |
| 3.4 | Configuration profiles cannot be changed by the user, and "Erase all content" is blocked (IT wipes through Intune) |
| 3.5 | Host pairing blocked (no data extraction over USB to an unknown computer) |
| 3.6 | Device wipes after 10 failed passcode attempts |

## 4. App protection (every iOS device with Microsoft 365 data)

| # | Requirement |
|---|---|
| 4.1 | Data moves only between policy-managed apps; clipboard out is limited to managed apps |
| 4.2 | No backup of app data, and no Save As to personal storage |
| 4.3 | App PIN of 6+ digits (biometrics allowed); re-check every 30 min online, 12 h offline |
| 4.4 | App data wiped after 90 days without a check-in |
| 4.5 | Corporate links open in Microsoft Edge |
| 4.6 | App minimum OS is no stricter than device compliance (personal devices are not locked out sooner than corporate ones) |

## 5. Conditional Access

| # | Requirement |
|---|---|
| 5.1 | Corporate iOS users reach Microsoft 365 only from a compliant device |
| 5.2 | All iOS access to Microsoft 365 comes from an app with app protection |
| 5.3 | Break-glass accounts are excluded from both |
| 5.4 | New or changed policies run report-only first |

## Exceptions

Exceptions are time-limited (90 days maximum). Each one has a risk owner and an assigned exception group with a review date, and
is recorded in the ticketing system. The validator has no exception mechanism on purpose: exceptions live in group membership, not in the baseline.
