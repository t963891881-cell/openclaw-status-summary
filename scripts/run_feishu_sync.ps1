$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$envFile = Join-Path $skillDir ".feishu_sync.env"

if (-not (Test-Path $envFile)) {
    Write-Error "Missing env file: $envFile"
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
        return
    }
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) {
        [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "python or python3 was not found in PATH"
}

& $python.Source (Join-Path $scriptDir "sync_feishu_bitable.py") `
    --app-id $env:APP_ID `
    --app-secret $env:APP_SECRET `
    --app-token $env:APP_TOKEN
