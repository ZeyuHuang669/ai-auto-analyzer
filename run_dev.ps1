# 一键启动：后端 + 前端各开一个 PowerShell 窗口
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "找不到虚拟环境：$python"
    exit 1
}

Start-Process pwsh -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$root\backend'; Set-Location '$root\backend'; & '$python' -m uvicorn app.main:app --reload --port 8000"
)

Start-Sleep -Seconds 3

Start-Process pwsh -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$root\front'; & '$python' -m streamlit run app.py"
)

Write-Host "后端: http://127.0.0.1:8000/docs"
Write-Host "前端: http://localhost:8501"
