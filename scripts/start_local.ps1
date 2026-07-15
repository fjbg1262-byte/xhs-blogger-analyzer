param(
  [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$logsDir = Join-Path $root "logs"
$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $root "requirements.txt"
$setupMarker = Join-Path $venvDir ".requirements-installed"
$frontendDir = Join-Path $root "frontend"
$spiderDir = Join-Path $root "spider_xhs"

function Write-Title($Text) {
  Write-Host ""
  Write-Host "============================================"
  Write-Host $Text
  Write-Host "============================================"
}

function Write-Step($Text) {
  Write-Host ""
  Write-Host "[*] $Text"
}

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Clear-BrokenLocalProxy {
  $proxyVars = @("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
  foreach ($name in $proxyVars) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not $value) {
      $value = [Environment]::GetEnvironmentVariable($name, "User")
    }
    if (-not $value) {
      continue
    }

    try {
      $uri = [Uri]$value
      $isLocal = $uri.Host -in @("127.0.0.1", "localhost")
      if ($isLocal -and $uri.Port -gt 0) {
        $alive = Test-NetConnection -ComputerName $uri.Host -Port $uri.Port -InformationLevel Quiet
        if (-not $alive) {
          Write-Step "Ignoring unavailable local proxy $value"
          Remove-Item "Env:$name" -ErrorAction SilentlyContinue
        }
      }
    } catch {
      continue
    }
  }
}

function Invoke-Step($FilePath, $Arguments, $WorkingDirectory) {
  $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -Wait -PassThru -NoNewWindow
  if ($process.ExitCode -ne 0) {
    throw "Command failed: $FilePath $($Arguments -join ' ')"
  }
}

function Get-PythonCommand {
  if (Test-Command "py") {
    return @{ File = "py"; Args = @("-3") }
  }
  if (Test-Command "python") {
    return @{ File = "python"; Args = @() }
  }
  return $null
}

function Test-Url($Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Wait-Url($Url, $Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-Url $Url) {
      return $true
    }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Ensure-Python {
  $python = Get-PythonCommand
  if (-not $python) {
    Write-Host ""
    Write-Host "Python was not found."
    Write-Host "Please install Python 3.9 or newer, then run this file again."
    Write-Host "Opening download page..."
    Start-Process "https://www.python.org/downloads/"
    throw "Missing Python"
  }

  if (-not (Test-Path $venvPython)) {
    Write-Step "Creating local Python environment"
    $args = @($python.Args) + @("-m", "venv", $venvDir)
    Invoke-Step $python.File $args $root
  }

  if (-not (Test-Path $setupMarker) -or (Get-Item $setupMarker).LastWriteTime -lt (Get-Item $requirements).LastWriteTime) {
    Write-Step "Installing Python packages"
    Invoke-Step $venvPython @("-m", "pip", "install", "--disable-pip-version-check", "-r", $requirements) $root
    New-Item -ItemType File -Force -Path $setupMarker | Out-Null
  }
}

function Ensure-NodePackages {
  if (-not (Test-Command "npm")) {
    Write-Host ""
    Write-Host "Node.js was not found."
    Write-Host "Please install Node.js LTS, then run this file again."
    Write-Host "Opening download page..."
    Start-Process "https://nodejs.org/"
    throw "Missing Node.js"
  }

  if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Step "Installing frontend packages"
    Invoke-Step "cmd.exe" @("/c", "npm install") $frontendDir
  }

  if ((Test-Path (Join-Path $spiderDir "package.json")) -and -not (Test-Path (Join-Path $spiderDir "node_modules"))) {
    Write-Step "Installing collector packages"
    Invoke-Step "cmd.exe" @("/c", "npm install") $spiderDir
  }
}

function Start-Backend {
  if (Test-Url "http://127.0.0.1:8000/api/health") {
    Write-Step "Backend is already running"
    return
  }

  Write-Step "Starting backend service"
  Start-Process `
    -FilePath $venvPython `
    -ArgumentList @("-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $root `
    -RedirectStandardOutput (Join-Path $logsDir "backend.log") `
    -RedirectStandardError (Join-Path $logsDir "backend.err.log") `
    -WindowStyle Hidden | Out-Null
}

function Start-Frontend {
  if (Test-Url "http://127.0.0.1:5173") {
    Write-Step "Frontend is already running"
    return
  }

  Write-Step "Starting frontend service"
  Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @("/c", "npm run dev -- --host 127.0.0.1") `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput (Join-Path $logsDir "frontend.log") `
    -RedirectStandardError (Join-Path $logsDir "frontend.err.log") `
    -WindowStyle Hidden | Out-Null
}

Write-Title "XHS Blogger Analyzer"
Write-Host "This launcher will prepare dependencies, start the local tool, and open the browser."

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
Clear-BrokenLocalProxy

Ensure-Python
Ensure-NodePackages

if ($InstallOnly) {
  Write-Host ""
  Write-Host "Setup finished. You can now double-click start_windows.bat."
  exit 0
}

Start-Backend
Start-Frontend

Write-Step "Waiting for local services"
$backendReady = Wait-Url "http://127.0.0.1:8000/api/health" 30
$frontendReady = Wait-Url "http://127.0.0.1:5173" 45

if (-not $backendReady -or -not $frontendReady) {
  Write-Host ""
  Write-Host "The local tool did not start successfully."
  Write-Host "Please check logs in:"
  Write-Host $logsDir
  throw "Local service startup failed"
}

Write-Host ""
Write-Host "Local tool is ready."
Write-Host "Opening browser: http://127.0.0.1:5173"
Start-Process "http://127.0.0.1:5173"
Write-Host ""
Write-Host "You can close this window. To stop the local tool later, double-click stop_windows.bat."
