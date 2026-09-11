# -*- coding: utf-8 -*-
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== 银月工坊：一镜到底录屏智能转录管家 环境自检 ===" -ForegroundColor Cyan

# 1. 检查 Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Python 已安装: $(python --version)" -ForegroundColor Green
} else {
    Write-Host "[ERROR] 未检测到 Python，请先配置 Python 环境！" -ForegroundColor Red
    exit 1
}

# 2. 检查 FFmpeg
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "[OK] FFmpeg 已安装并加入 PATH" -ForegroundColor Green
} else {
    Write-Host "[ERROR] 未检测到 FFmpeg！" -ForegroundColor Red
    exit 1
}

# 3. 检查 Python 依赖
$packages = @("soundfile", "numpy", "websockets")
foreach ($pkg in $packages) {
    $check = python -c "import $pkg" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python 模块: $pkg" -ForegroundColor Green
    } else {
        Write-Host "[WARN] 正在安装 Python 模块: $pkg ..." -ForegroundColor Yellow
        pip install $pkg
    }
}

# 4. 检查 SayIt 核心
$sayitScript = "D:\我的电脑工具库\03_系统与网络法宝\SayIt语音与鼠标守护管家\scripts\sayit_clipboard_guardian.py"
if (Test-Path $sayitScript) {
    Write-Host "[OK] SayIt 守护管家核心已定位" -ForegroundColor Green
} else {
    Write-Host "[WARN] 未在标准路径检测到 SayIt 守护管家脚本: $sayitScript" -ForegroundColor Yellow
}

Write-Host "`n>>> 环境自检完成，一切就绪！双击 run.bat 即可一键转录！" -ForegroundColor Green
