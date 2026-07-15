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
$frontendDist = Join-Path $frontendDir "dist"
$frontendIndex = Join-Path $frontendDist "index.html"
$spiderDir = Join-Path $root "spider_xhs"
$backendLog = Join-Path $logsDir "backend.log"
$backendErr = Join-Path $logsDir "backend.err.log"
$setupLog = Join-Path $logsDir "setup.log"
$setupErr = Join-Path $logsDir "setup.err.log"

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

function Write-Ok($Text) {
  Write-Host "[OK] $Text"
}

function Write-Warn($Text) {
  Write-Host "[!] $Text"
}

function Fail-User($Title, $Detail) {
  Write-Host ""
  Write-Host "[FAILED] $Title"
  if ($Detail) {
    Write-Host $Detail
  }
  Write-Host ""
  Write-Host "Please send this logs folder to the author if you need help:"
  Write-Host $logsDir
  throw $Title
}

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-TcpPort($HostName, $Port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect($HostName, $Port, $null, $null)
    $success = $async.AsyncWaitHandle.WaitOne(800, $false)
    if (-not $success) {
      return $false
    }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
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
      if ($isLocal -and $uri.Port -gt 0 -and -not (Test-TcpPort $uri.Host $uri.Port)) {
        Write-Warn "Unavailable local proxy ignored for this launch: $value"
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
      }
    } catch {
      continue
    }
  }
}

function Invoke-LoggedStep($FilePath, $Arguments, $WorkingDirectory, $Name) {
  Add-Content -Path $setupLog -Value ""
  Add-Content -Path $setupLog -Value "===== $Name ====="
  Add-Content -Path $setupLog -Value "$FilePath $($Arguments -join ' ')"
  Add-Content -Path $setupErr -Value ""
  Add-Content -Path $setupErr -Value "===== $Name ====="

  $process = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $Arguments `
    -WorkingDirectory $WorkingDirectory `
    -Wait `
    -PassThru `
    -NoNewWindow `
    -RedirectStandardOutput $setupLog `
    -RedirectStandardError $setupErr

  if ($process.ExitCode -ne 0) {
    Fail-User "$Name failed" "Check your network, then check: $setupErr"
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

function Test-PortFreeOrExpected($Port, $HealthUrl, $ServiceName) {
  if (Test-Url $HealthUrl) {
    return "ready"
  }

  if (Test-TcpPort "127.0.0.1" $Port) {
    Fail-User "$ServiceName port is busy" "Port $Port is used by another program. Close that program or restart Windows, then try again."
  }

  return "free"
}

function Ensure-Python {
  $python = Get-PythonCommand
  if (-not $python) {
    Start-Process "https://www.python.org/downloads/"
    Fail-User "Python was not found" "Install Python 3.9 or newer. During installation, tick Add Python to PATH."
  }

  if (-not (Test-Path $venvPython)) {
    Write-Step "First launch: creating local Python environment"
    $args = @($python.Args) + @("-m", "venv", $venvDir)
    Invoke-LoggedStep $python.File $args $root "Create local Python environment"
  }

  if (-not (Test-Path $setupMarker) -or (Get-Item $setupMarker).LastWriteTime -lt (Get-Item $requirements).LastWriteTime) {
    Write-Step "Installing Python packages. First launch may take 5-15 minutes. Do not close this window."
    Invoke-LoggedStep $venvPython @("-m", "pip", "install", "--disable-pip-version-check", "-r", $requirements) $root "Install Python packages"
    New-Item -ItemType File -Force -Path $setupMarker | Out-Null
  } else {
    Write-Ok "Python packages are ready"
  }
}

function Ensure-FrontendBuild {
  if (Test-Path $frontendIndex) {
    Write-Ok "Web page build is ready"
    return
  }

  if (-not (Test-Command "npm")) {
    Start-Process "https://nodejs.org/"
    Fail-User "Web page build was not found" "Use the packaged beta zip that includes frontend/dist, or install Node.js LTS to build the web page once."
  }

  if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Step "Installing web packages to build the local page. First launch may take a few minutes."
    Invoke-LoggedStep "cmd.exe" @("/c", "npm install") $frontendDir "Install web packages"
  } else {
    Write-Ok "Web packages are ready"
  }

  Write-Step "Building local web page assets"
  Invoke-LoggedStep "cmd.exe" @("/c", "npm run build") $frontendDir "Build web page"

  if (-not (Test-Path $frontendIndex)) {
    Fail-User "Web page build failed" "Expected file was not created: $frontendIndex"
  }
}

function Ensure-CollectorPackages {
  if (-not (Test-Path (Join-Path $spiderDir "package.json"))) {
    return
  }

  if (Test-Path (Join-Path $spiderDir "node_modules")) {
    Write-Ok "Collector packages are ready"
    return
  }

  if (-not (Test-Command "npm")) {
    Write-Warn "Collector packages are missing and npm was not found. The page can open, but analysis may fail until the next packaging phase bundles this dependency."
    return
  }

  Write-Step "Installing collector packages. First launch may take a few minutes. Do not close this window."
  Invoke-LoggedStep "cmd.exe" @("/c", "npm install") $spiderDir "Install collector packages"
}

function Start-Backend {
  $state = Test-PortFreeOrExpected 8000 "http://127.0.0.1:8000/api/health" "Backend"
  if ($state -eq "ready") {
    Write-Ok "Backend service is already running"
    return
  }

  Write-Step "Starting backend service"
  Start-Process `
    -FilePath $venvPython `
    -ArgumentList @("-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden | Out-Null
}

Write-Title "XHS Blogger Analyzer"
Write-Host "This launcher prepares the local tool, starts services, and opens the browser."
Write-Host "First launch can be slow. Please keep this window open."

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
Clear-BrokenLocalProxy

Ensure-Python
Ensure-FrontendBuild
Ensure-CollectorPackages

if ($InstallOnly) {
  Write-Host ""
  Write-Ok "Setup finished. Next time, double-click start_windows.bat."
  exit 0
}

Start-Backend

Write-Step "Waiting for local services"
$backendReady = Wait-Url "http://127.0.0.1:8000/api/health" 30
$webReady = Wait-Url "http://127.0.0.1:8000" 30

if (-not $backendReady -or -not $webReady) {
  Fail-User "Local tool did not start" "Check logs in: $logsDir"
}

Write-Host ""
Write-Ok "Local tool is ready"
Write-Host "Opening browser: http://127.0.0.1:8000"
Start-Process "http://127.0.0.1:8000"
Write-Host ""
Write-Host "You can close this window. To stop the local tool later, double-click stop_windows.bat."
