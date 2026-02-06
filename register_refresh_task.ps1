param(
    [string]$Time = "03:00"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "ICU-Hemodynamic-Refresh"
$scriptPath = Join-Path $root "refresh.ps1"

# Use New-ScheduledTask* cmdlets to avoid schtasks quoting issues with
# paths containing spaces.  These handle argument escaping internally.
$taskAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time

Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger -Force

Write-Host "Scheduled task '$taskName' created to run daily at $Time."
