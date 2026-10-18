@echo off
setlocal
REM 绕过 PowerShell ExecutionPolicy，Windows 推荐用本文件启动
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
exit /b %ERRORLEVEL%
