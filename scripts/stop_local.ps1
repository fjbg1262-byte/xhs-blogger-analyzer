$ErrorActionPreference = "SilentlyContinue"

function Stop-Port($Port) {
  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen
  foreach ($connection in $connections) {
    $processId = $connection.OwningProcess
    if ($processId) {
      Stop-Process -Id $processId -Force
    }
  }
}

Write-Host ""
Write-Host "Stopping XHS Blogger Analyzer local services..."
Stop-Port 8000
Stop-Port 5173
Write-Host "Stopped. You can close this window."
