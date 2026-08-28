Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Atlas Python stopped. Docker left running."
