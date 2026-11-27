#Requires -Version 7.2
#Requires -Modules Microsoft.Graph.Authentication
<#
.SYNOPSIS
    Read-only export of iOS / iPadOS managed devices from Intune, in the column layout tools/fleet_report.py reads.
.NOTES
    Delegated scope: DeviceManagementManagedDevices.Read.All
.EXAMPLE
    Connect-MgGraph -Scopes DeviceManagementManagedDevices.Read.All
    ./scripts/Export-ManagedDevices.ps1 -OutFile ./data/live/managed_devices.csv
    python3 tools/fleet_report.py --data ./data/live --out ./out
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$OutFile)
$ErrorActionPreference = 'Stop'

$select = 'id,deviceName,serialNumber,model,operatingSystem,osVersion,userPrincipalName,managedDeviceOwnerType,' +
'deviceEnrollmentType,isSupervised,complianceState,jailBroken,isEncrypted,enrolledDateTime,lastSyncDateTime,partnerReportedThreatState'
$uri = "/v1.0/deviceManagement/managedDevices?`$filter=operatingSystem eq 'iOS' or operatingSystem eq 'iPadOS'&`$select=$select&`$top=999"

$rows = [System.Collections.Generic.List[object]]::new()
while ($uri) {
    $page = Invoke-MgGraphRequest -Uri $uri -OutputType Hashtable
    foreach ($d in $page.value) {
        $rows.Add([pscustomobject]@{
                id = $d.id; deviceName = $d.deviceName; serialNumber = $d.serialNumber; model = $d.model
                operatingSystem = $d.operatingSystem; osVersion = $d.osVersion; userPrincipalName = $d.userPrincipalName
                department = ''                                            # join from Entra user if needed
                managedDeviceOwnerType = $d.managedDeviceOwnerType; deviceEnrollmentType = $d.deviceEnrollmentType
                isSupervised = $d.isSupervised; complianceState = $d.complianceState
                nonCompliantSettings = ''                                  # filled below for non-compliant devices
                jailBroken = $d.jailBroken; isEncrypted = $d.isEncrypted
                enrolledDateTime = ([datetime]$d.enrolledDateTime).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
                lastSyncDateTime = ([datetime]$d.lastSyncDateTime).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
                partnerReportedThreatState = $d.partnerReportedThreatState
            })
    }
    $uri = $page['@odata.nextLink']
}

# Per-setting reasons for non-compliant devices
foreach ($r in $rows | Where-Object { $_.complianceState -eq 'noncompliant' }) {
    $states = (Invoke-MgGraphRequest -Uri "/v1.0/deviceManagement/managedDevices/$($r.id)/deviceCompliancePolicyStates" -OutputType Hashtable).value
    $reasons = foreach ($s in $states) {
        foreach ($setting in $s.settingStates) {
            if ($setting.state -eq 'nonCompliant') { ($setting.setting -split '\.')[-1] }
        }
    }
    $r.nonCompliantSettings = (@($reasons) | Sort-Object -Unique) -join ';'
}

New-Item -ItemType Directory -Force -Path (Split-Path $OutFile) | Out-Null
$rows | Export-Csv -Path $OutFile -NoTypeInformation
Write-Host "Exported $($rows.Count) iOS/iPadOS devices to $OutFile"
