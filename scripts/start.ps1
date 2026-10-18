#Requires -Version 5.1
<#
.SYNOPSIS
  一键启动 API + Web（Windows）
.EXAMPLE
  .\start.cmd -Demo
  powershell -ExecutionPolicy Bypass -File .\start.ps1 -Demo
#>
param(
    [switch]$Demo,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

# 兼容 bash 风格 --demo
if ($Rest -contains "--demo" -or $Rest -contains "-demo") {
    $Demo = $true
}

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root ".run") | Out-Null

# stop previous
& (Join-Path $PSScriptRoot "stop.ps1") 2>$null | Out-Null

$venvPy = Join-Path $Root "backend\.venv\Scripts\python.exe"
$venvPip = Join-Path $Root "backend\.venv\Scripts\pip.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "[start] creating venv..."
    python -m venv (Join-Path $Root "backend\.venv")
    & $venvPip install -U pip
    & $venvPip install -r (Join-Path $Root "backend\requirements.txt")
}

$webModules = Join-Path $Root "web\node_modules"
if (-not (Test-Path $webModules)) {
    Write-Host "[start] npm install..."
    Push-Location (Join-Path $Root "web")
    npm install
    Pop-Location
}

$env:ASHARE_DEMO_MODE = if ($Demo) { "1" } else { "0" }
$env:ASHARE_CACHE_TTL = if ($env:ASHARE_CACHE_TTL) { $env:ASHARE_CACHE_TTL } else { "300" }

Write-Host "[start] API on :8000 (ASHARE_DEMO_MODE=$($env:ASHARE_DEMO_MODE))"
$apiOut = Join-Path $Root ".run\api.out.log"
$apiErr = Join-Path $Root ".run\api.err.log"
$api = Start-Process -FilePath $venvPy `
    -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--app-dir", (Join-Path $Root "backend"),
        "--host", "0.0.0.0", "--port", "8000"
    ) `
    -WorkingDirectory (Join-Path $Root "backend") `
    -WindowStyle Hidden `
    -RedirectStandardOutput $apiOut `
    -RedirectStandardError $apiErr `
    -PassThru
Set-Content -Path (Join-Path $Root ".run\api.pid") -Value $api.Id

Write-Host "[start] Web on :5173"
$webOut = Join-Path $Root ".run\web.out.log"
$webErr = Join-Path $Root ".run\web.err.log"
# Windows 上 npm 通常是 npm.cmd，经 cmd 启动更稳
$webCmd = "npm --prefix `"$(Join-Path $Root 'web')`" run dev -- --host 0.0.0.0 --port 5173"
$web = Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", $webCmd) `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $webOut `
    -RedirectStandardError $webErr `
    -PassThru
Set-Content -Path (Join-Path $Root ".run\web.pid") -Value $web.Id

$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $ok) {
    Write-Host "[err] API 未就绪，查看日志: $apiErr" -ForegroundColor Red
    Get-Content $apiErr -ErrorAction SilentlyContinue | Select-Object -Last 30
    exit 1
}

Write-Host "[ok] API healthy"
Write-Host "[ok] Web: http://127.0.0.1:5173"
Write-Host "[ok] API docs: http://127.0.0.1:8000/docs"
Write-Host "Logs: $apiOut / $apiErr , $webOut / $webErr"
Write-Host ""
Write-Host "Android Studio: 打开仓库 android/ 目录；模拟器默认连 http://10.0.2.2:8000"
Write-Host "真机调试: 在 android/local.properties 设置 ashare.api.baseUrl=http://<电脑局域网IP>:8000"
