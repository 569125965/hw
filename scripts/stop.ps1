#Requires -Version 5.1
$ErrorActionPreference = "SilentlyContinue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$run = Join-Path $Root ".run"
New-Item -ItemType Directory -Force -Path $run | Out-Null

function Stop-PidFile([string]$file) {
    if (-not (Test-Path $file)) { return }
    $pidText = Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidText -match '^\d+$') {
        $procId = [int]$pidText
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    Remove-Item $file -Force -ErrorAction SilentlyContinue
}

Stop-PidFile (Join-Path $run "api.pid")
Stop-PidFile (Join-Path $run "web.pid")

# fallback: kill listeners on ports
foreach ($port in 8000, 5173) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Write-Host "[ok] stopped"
