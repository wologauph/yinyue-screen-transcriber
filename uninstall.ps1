# ==============================================================================
# 一键卸载与清理脚本 (Uninstall Script)
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ">>> 清理开机启动项..." -ForegroundColor Cyan
$startupFolder = [Environment]::GetFolderPath('Startup')
$projectName = (Get-Item $PSScriptRoot).Name
$batInStartup = Join-Path $startupFolder "$projectName.bat"

if (Test-Path $batInStartup) {
    Remove-Item $batInStartup -Force
    Write-Host "已移除开机启动: $batInStartup" -ForegroundColor Green
}

Write-Host ">>> 清理完成。如需彻底删除项目，直接删除本文件夹即可，无任何注册表残留！" -ForegroundColor Green
