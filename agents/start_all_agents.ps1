# ╔══════════════════════════════════════════════════════════╗
# ║  TRISASTRA AI — Start All 14 Agents (PowerShell)         ║
# ║  Runs all 14 agents as background processes              ║
# ╚══════════════════════════════════════════════════════════╝

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Detect Python interpreter (prefer backend/venv if present)
$VenvPython = Join-Path $ScriptDir "..\backend\venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonBin = (Resolve-Path $VenvPython).Path
    Write-Host "Using virtualenv Python: $PythonBin" -ForegroundColor Green
} else {
    $PythonBin = "python"
    Write-Host "Using system Python: python" -ForegroundColor Yellow
}

# Ensure logs directory exists
$LogsDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$Agents = @(
    "pan-agent",
    "compliance-agent",
    "doc-agent",
    "pd-agent",
    "gst-agent",
    "bank-recon-agent",
    "mca-agent",
    "web-agent",
    "model-selector-agent",
    "risk-agent",
    "bias-agent",
    "stress-agent",
    "cam-agent",
    "monitor-agent"
)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  TRISASTRA AI - Starting All 14 AI Agents              " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$Processes = @()

foreach ($Agent in $Agents) {
    $AgentScript = Join-Path $ScriptDir "$Agent\main.py"
    if (Test-Path $AgentScript) {
        $LogFile = Join-Path $LogsDir "$Agent.log"
        $procParams = @{
            FilePath               = $PythonBin
            ArgumentList           = $AgentScript
            WorkingDirectory       = $ScriptDir
            RedirectStandardOutput = $LogFile
            RedirectStandardError  = $LogFile
            PassThru               = $true
            NoNewWindow            = $true
        }
        $Proc = Start-Process @procParams
        $Processes += $Proc
        Write-Host "  [OK] Started $Agent (PID: $($Proc.Id))" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] Script not found: $AgentScript" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  All $($Processes.Count) agents started in background!" -ForegroundColor Green
Write-Host "  Logs: agents\logs\<agent-name>.log" -ForegroundColor Gray
Write-Host "  To stop all agents, press Ctrl+C or run:" -ForegroundColor Gray
Write-Host "    Get-Process python | Stop-Process" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

try {
    while ($true) {
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host ""
    Write-Host "Stopping all agents..." -ForegroundColor Yellow
    foreach ($Proc in $Processes) {
        try {
            Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Write-Host "All agent processes stopped." -ForegroundColor Green
}
