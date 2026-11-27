#Requires -Version 7.2
#Requires -Modules Microsoft.Graph.Authentication
<#
.SYNOPSIS
    Deploys the iOS baseline (compliance, device restrictions, app protection, Conditional Access) to Intune / Entra ID
    and assigns it to a deployment ring.

.DESCRIPTION
    Each object is matched by displayName. If it exists it is updated (PATCH), otherwise it is created (POST), so
    re-running is safe. Conditional Access policies are always created in report-only mode. Switching them to
    "enabled" is a separate, deliberate step (-EnableConditionalAccess) after the report-only review.

      compliance-ios.json       POST/PATCH /deviceManagement/deviceCompliancePolicies         + /assign
      restrictions-ios.json     POST/PATCH /deviceManagement/deviceConfigurations             + /assign
      app-protection-ios.json   POST/PATCH /deviceAppManagement/iosManagedAppProtections      + /targetApps + /assign
      conditional-access.json   POST/PATCH /identity/conditionalAccess/policies

    The ADE enrollment profile is created in the Intune admin center against the ABM token (beta API), using
    baseline/enrollment-ade.json as the documented settings.

.PARAMETER Ring
    0 = IT pilot, 1 = early adopters, 2 = broad (the groups in baseline/assignments.json).

.NOTES
    Delegated scopes: DeviceManagementConfiguration.ReadWrite.All, DeviceManagementApps.ReadWrite.All,
    Policy.ReadWrite.ConditionalAccess, Policy.Read.All, Group.Read.All
.EXAMPLE
    ./scripts/Deploy-IntuneBaseline.ps1 -Ring 0 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet(0, 1, 2)][int]$Ring = 0,
    [switch]$EnableConditionalAccess,
    [string]$BaselinePath = (Join-Path $PSScriptRoot '..' 'baseline')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-Baseline([string]$Name) { Get-Content -Raw (Join-Path $BaselinePath $Name) | ConvertFrom-Json -AsHashtable }

function Invoke-Graph {
    param([string]$Method = 'GET', [string]$Uri, $Body)
    $p = @{ Method = $Method; Uri = $Uri; OutputType = 'Hashtable' }
    if ($null -ne $Body) { $p.Body = $Body | ConvertTo-Json -Depth 20; $p.ContentType = 'application/json' }
    Invoke-MgGraphRequest @p
}

function Get-ByName([string]$Collection, [string]$Name) {
    $escaped = $Name.Replace("'", "''")
    @((Invoke-Graph -Uri "$Collection`?`$filter=displayName eq '$escaped'").value) | Select-Object -First 1
}

function Get-GroupId([string]$Name) {
    $escaped = $Name.Replace("'", "''")
    $g = @((Invoke-Graph -Uri "/v1.0/groups?`$filter=displayName eq '$escaped'&`$select=id").value)
    if ($g.Count -ne 1) { throw "Expected one group named '$Name', found $($g.Count)." }
    $g[0].id
}

function Set-BaselineObject {
    param([string]$Collection, [hashtable]$Body, [string]$Kind)
    $existing = Get-ByName -Collection $Collection -Name $Body.displayName
    if ($existing) {
        if ($PSCmdlet.ShouldProcess($Body.displayName, "Update $Kind")) {
            $patch = $Body.Clone()
            $patch.Remove('scheduledActionsForRule')        # only accepted on create
            Invoke-Graph -Method PATCH -Uri "$Collection/$($existing.id)" -Body $patch | Out-Null
        }
        return $existing.id
    }
    if ($PSCmdlet.ShouldProcess($Body.displayName, "Create $Kind")) {
        return (Invoke-Graph -Method POST -Uri $Collection -Body $Body).id
    }
}

$asg = Read-Baseline 'assignments.json'
$ringGroup = $asg.rings[$Ring].group
Write-Host "Deploying iOS baseline to $($asg.rings[$Ring].name) ($ringGroup)"
$ringGroupId = if ($WhatIfPreference) { '<ring-group-id>' } else { Get-GroupId $ringGroup }
$target = @{ '@odata.type' = '#microsoft.graph.groupAssignmentTarget'; groupId = $ringGroupId }

# ---- compliance
$compliance = Read-Baseline 'compliance-ios.json'
$id = Set-BaselineObject -Collection '/v1.0/deviceManagement/deviceCompliancePolicies' -Body $compliance -Kind 'compliance policy'
if ($id -and $PSCmdlet.ShouldProcess($compliance.displayName, "Assign to $ringGroup")) {
    Invoke-Graph -Method POST -Uri "/v1.0/deviceManagement/deviceCompliancePolicies/$id/assign" -Body @{
        assignments = @(@{ target = $target }) } | Out-Null
}

# ---- device restrictions
$restrictions = Read-Baseline 'restrictions-ios.json'
$id = Set-BaselineObject -Collection '/v1.0/deviceManagement/deviceConfigurations' -Body $restrictions -Kind 'device configuration'
if ($id -and $PSCmdlet.ShouldProcess($restrictions.displayName, "Assign to $ringGroup")) {
    Invoke-Graph -Method POST -Uri "/v1.0/deviceManagement/deviceConfigurations/$id/assign" -Body @{
        assignments = @(@{ target = $target }) } | Out-Null
}

# ---- app protection (users, not devices: assigned to the MAM group, independent of ring)
$app = Read-Baseline 'app-protection-ios.json'
$bundleIds = $app.apps; $app.Remove('apps')
$id = Set-BaselineObject -Collection '/v1.0/deviceAppManagement/iosManagedAppProtections' -Body $app -Kind 'app protection policy'
if ($id -and $PSCmdlet.ShouldProcess("$($app.displayName): $($bundleIds.Count) apps", 'Set target apps and assignment')) {
    Invoke-Graph -Method POST -Uri "/v1.0/deviceAppManagement/iosManagedAppProtections/$id/targetApps" -Body @{
        apps = @($bundleIds | ForEach-Object {
                @{ mobileAppIdentifier = @{ '@odata.type' = '#microsoft.graph.iosMobileAppIdentifier'; bundleId = $_ } } })
    } | Out-Null
    $mamGroup = Get-GroupId $asg.assignments['app-protection-ios.json'][0]
    Invoke-Graph -Method POST -Uri "/v1.0/deviceAppManagement/iosManagedAppProtections/$id/assign" -Body @{
        assignments = @(@{ target = @{ '@odata.type' = '#microsoft.graph.groupAssignmentTarget'; groupId = $mamGroup } }) } | Out-Null
}

# ---- conditional access (report-only unless explicitly enabled)
foreach ($p in (Read-Baseline 'conditional-access.json').policies) {
    $users = $p.conditions.users
    $body = @{
        displayName   = $p.displayName
        state         = if ($EnableConditionalAccess) { 'enabled' } else { 'enabledForReportingButNotEnforced' }
        conditions    = @{
            users          = @{
                includeUsers  = @($users['includeUsers'] ?? @())
                includeGroups = @(if (-not $WhatIfPreference) { ($users['includeGroups'] ?? @()) | ForEach-Object { Get-GroupId $_ } })
                excludeGroups = @(if (-not $WhatIfPreference) { ($users['excludeGroups'] ?? @()) | ForEach-Object { Get-GroupId $_ } })
            }
            applications   = $p.conditions.applications
            platforms      = $p.conditions.platforms
            clientAppTypes = $p.conditions.clientAppTypes
        }
        grantControls = $p.grantControls
    }
    if (-not $body.conditions.users.includeUsers.Count) { $body.conditions.users.Remove('includeUsers') }
    Set-BaselineObject -Collection '/v1.0/identity/conditionalAccess/policies' -Body $body -Kind "CA policy ($($body.state))" | Out-Null
}

Write-Host 'Done. Check device check-in status in Intune and the CA report-only results in sign-in logs before the next ring.'
