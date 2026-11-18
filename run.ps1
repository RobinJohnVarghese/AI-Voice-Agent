Set-Location $PSScriptRoot
$env:PHONEMIZER_ESPEAK_LIBRARY = "C:\Program Files\eSpeak NG\libespeak-ng.dll"
$env:PATH += ";C:\Program Files\eSpeak NG"
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags | Out-Null } catch { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep 4 }
.\.venv\Scripts\uvicorn app.server:app --host 127.0.0.1 --port 8000
