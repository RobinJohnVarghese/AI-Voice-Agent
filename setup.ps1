# One-command setup for Windows 10/11 (PowerShell). Run:  powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> System packages via winget (Python, eSpeak NG, FFmpeg, Ollama)"
$pkgs = @("Python.Python.3.11", "eSpeak-NG.eSpeak-NG", "Gyan.FFmpeg", "Ollama.Ollama")
foreach ($p in $pkgs) {
  winget install --id $p -e --accept-package-agreements --accept-source-agreements --silent 2>$null | Out-Null
}
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

$espeakDll = "C:\Program Files\eSpeak NG\libespeak-ng.dll"
if (Test-Path $espeakDll) {
  [Environment]::SetEnvironmentVariable("PHONEMIZER_ESPEAK_LIBRARY", $espeakDll, "User")
  [Environment]::SetEnvironmentVariable("PHONEMIZER_ESPEAK_PATH", "C:\Program Files\eSpeak NG", "User")
  $env:PHONEMIZER_ESPEAK_LIBRARY = $espeakDll
  $env:PATH += ";C:\Program Files\eSpeak NG"
}

Write-Host "==> Ollama service"
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags | Out-Null } catch { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep 4 }

Write-Host "==> Python environment"
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -q --upgrade pip
.\.venv\Scripts\pip install -q -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "==> Models (one-time download)"
.\.venv\Scripts\python download_models.py @args

Write-Host "`nDone. Start with: .\run.ps1   then open http://127.0.0.1:8000"
