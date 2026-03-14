$taskName = "OpenClawFeishuSync"
$repoRoot = "C:\path\to\openclaw-status-summary"
$scriptPath = Join-Path $repoRoot "scripts\run_feishu_sync.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
$settings = New-ScheduledTaskSettingsSet

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings

Write-Host "Task created: $taskName"
Write-Host "Adjust repetition in Task Scheduler UI or extend this script for a 5-minute repeat window."
