$ErrorActionPreference = "SilentlyContinue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Test-OwnedProcess($ProcessId) {
  $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
  if (-not $processInfo) {
    return $false
  }

  $commandLine = $processInfo.CommandLine
  if (-not $commandLine) {
    return $false
  }

  $rootText = $root.Path
  return (
    $commandLine.Contains($rootText) -or
    $commandLine.Contains("backend.app:app") -or
    $commandLine.Contains("npm run dev") -or
    $commandLine.Contains("vite")
  )
}

function Stop-Port($Port) {
  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen
  foreach ($connection in $connections) {
    $processId = $connection.OwningProcess
    if (-not $processId) {
      continue
    }

    if (Test-OwnedProcess $processId) {
      Stop-Process -Id $processId -Force
      Write-Host "[OK] Stopped local service on port $Port"
    } else {
      Write-Host "[!] Port $Port is used by another program. It was not stopped."
    }
  }
}

Write-Host ""
Write-Host "Stopping XHS Blogger Analyzer local services..."
Stop-Port 8000
Stop-Port 5173
Write-Host "Done. You can close this window."
