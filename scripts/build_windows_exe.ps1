param(
  [string]$Version = "windows",
  [switch]$SkipPyInstaller
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$releaseDir = Join-Path $root "release"
$finalDir = Join-Path $releaseDir "xhs-blogger-analyzer-$Version"
$buildDir = Join-Path $releaseDir "build-windows"
$distDir = Join-Path $buildDir "dist"
$workDir = Join-Path $buildDir "work"
$specDir = Join-Path $buildDir "spec"
$frontendDir = Join-Path $root "frontend"
$spiderDir = Join-Path $root "spider_xhs"

function Utf8Text($Base64) {
  return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($Base64))
}

$appName = Utf8Text "WEhT5YiG5p6Q5Yqp5omL"
$stopBatName = Utf8Text "5YWz6Zet5pys5Zyw5bel5YW3LmJhdA=="
$pyInstallerOut = Join-Path $distDir $appName

function Resolve-SafePath($Path) {
  if (Test-Path $Path) {
    return (Resolve-Path $Path).Path
  }
  return [System.IO.Path]::GetFullPath($Path)
}

function Remove-SafeDir($Path, $Parent) {
  if (-not (Test-Path $Path)) {
    return
  }
  $resolved = Resolve-SafePath $Path
  $resolvedParent = Resolve-SafePath $Parent
  if (-not $resolved.StartsWith($resolvedParent)) {
    throw "Refusing to remove unexpected path: $resolved"
  }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}

function Get-PythonExe {
  $venvPython = Join-Path $root ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }
  if (Get-Command "py" -ErrorAction SilentlyContinue) {
    return "py"
  }
  if (Get-Command "python" -ErrorAction SilentlyContinue) {
    return "python"
  }
  throw "Python was not found. Build machine needs Python, but end users will not."
}

function Invoke-Step($Title, $ScriptBlock) {
  Write-Host ""
  Write-Host "== $Title =="
  & $ScriptBlock
}

function Test-TcpPort($HostName, $Port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect($HostName, $Port, $null, $null)
    $success = $async.AsyncWaitHandle.WaitOne(800, $false)
    if (-not $success) { return $false }
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
    if (-not $value) { continue }

    try {
      $uri = [Uri]$value
      $isLocal = $uri.Host -in @("127.0.0.1", "localhost")
      if ($isLocal -and $uri.Port -gt 0 -and -not (Test-TcpPort $uri.Host $uri.Port)) {
        Write-Host "[!] Unavailable local proxy ignored for this build: $value"
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
      }
    } catch {
      continue
    }
  }
}

function Copy-Tree($Source, $Destination, [string[]]$ExcludeDirs = @(), [string[]]$ExcludeFiles = @()) {
  if (-not (Test-Path $Source)) {
    throw "Missing source: $Source"
  }
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  $args = @($Source, $Destination, "/E")
  if ($ExcludeDirs.Count -gt 0) {
    $args += "/XD"
    $args += $ExcludeDirs
  }
  if ($ExcludeFiles.Count -gt 0) {
    $args += "/XF"
    $args += $ExcludeFiles
  }
  robocopy @args | Out-Host
  if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed from $Source to $Destination with exit code $LASTEXITCODE"
  }
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Clear-BrokenLocalProxy
Remove-SafeDir $finalDir $releaseDir
Remove-SafeDir $buildDir $releaseDir
New-Item -ItemType Directory -Force -Path $finalDir | Out-Null
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

Invoke-Step "Build frontend/dist" {
  if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Build machine needs Node.js to build frontend assets."
  }
  Push-Location $frontendDir
  try {
    if (-not (Test-Path "node_modules")) {
      npm install
      if ($LASTEXITCODE -ne 0) { throw "npm install failed in frontend" }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed in frontend" }
  } finally {
    Pop-Location
  }
}

Invoke-Step "Prepare Spider_XHS node_modules" {
  if (-not (Test-Path (Join-Path $spiderDir "package.json"))) {
    throw "spider_xhs/package.json was not found"
  }
  if (-not (Test-Path (Join-Path $spiderDir "node_modules"))) {
    Push-Location $spiderDir
    try {
      npm install
      if ($LASTEXITCODE -ne 0) { throw "npm install failed in spider_xhs" }
    } finally {
      Pop-Location
    }
  }
}

$python = Get-PythonExe
Invoke-Step "Install PyInstaller on build machine" {
  & $python -m pip show pyinstaller | Out-Null
  if ($LASTEXITCODE -ne 0) {
    & $python -m pip install --disable-pip-version-check pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "Failed to install pyinstaller" }
  }
}

if (-not $SkipPyInstaller) {
  Invoke-Step "Build Windows exe with PyInstaller" {
    & $python -m PyInstaller `
      --noconfirm `
      --clean `
      --onedir `
      --name $appName `
      --distpath $distDir `
      --workpath $workDir `
      --specpath $specDir `
      --hidden-import uvicorn.logging `
      --hidden-import uvicorn.loops.auto `
      --hidden-import uvicorn.protocols.http.auto `
      --hidden-import uvicorn.protocols.websockets.auto `
      --hidden-import uvicorn.lifespan.on `
      --hidden-import httptools `
      --hidden-import websockets.legacy.server `
      --hidden-import sqlalchemy.sql.default_comparator `
      (Join-Path $root "desktop_entry.py")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
  }
}

if (-not (Test-Path $pyInstallerOut)) {
  throw "PyInstaller output was not found: $pyInstallerOut"
}

Invoke-Step "Copy executable runtime" {
  Copy-Tree $pyInstallerOut $finalDir
}

Invoke-Step "Copy app resources" {
  Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $finalDir "README.md") -Force
  Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination (Join-Path $finalDir ".env.example") -Force
  Copy-Item -LiteralPath (Join-Path $root "cookies.example.json") -Destination (Join-Path $finalDir "cookies.example.json") -Force
  Copy-Item -LiteralPath (Join-Path $root "analyze_all.py") -Destination (Join-Path $finalDir "analyze_all.py") -Force
  Copy-Item -LiteralPath (Join-Path $root "generate_reports.py") -Destination (Join-Path $finalDir "generate_reports.py") -Force

  Copy-Tree (Join-Path $root "browser-extension") (Join-Path $finalDir "browser-extension") `
    @("node_modules", "__pycache__", ".git") @("*.log", "*.pyc")
  Copy-Tree (Join-Path $root "docs") (Join-Path $finalDir "docs") `
    @("__pycache__", ".git") @("*.log", "*.pyc")
  Copy-Tree (Join-Path $root "static") (Join-Path $finalDir "static") `
    @("__pycache__", ".git") @("*.log", "*.pyc")

  New-Item -ItemType Directory -Force -Path (Join-Path $finalDir "frontend") | Out-Null
  Copy-Tree (Join-Path $frontendDir "dist") (Join-Path $finalDir "frontend\dist") `
    @("__pycache__", ".git") @("*.log", "*.pyc")

  Copy-Tree $spiderDir (Join-Path $finalDir "spider_xhs") `
    @("__pycache__", ".git", "logs", "data", "reports") `
    @(".env", "cookies.json", "*.log", "*.pyc", "*.tar.gz")
}

Invoke-Step "Copy portable Node runtime" {
  $nodeCommand = Get-Command "node" -ErrorAction SilentlyContinue
  if (-not $nodeCommand) {
    throw "node.exe was not found on build machine"
  }
  $nodeTargetDir = Join-Path $finalDir "runtime\node"
  New-Item -ItemType Directory -Force -Path $nodeTargetDir | Out-Null
  Copy-Item -LiteralPath $nodeCommand.Source -Destination (Join-Path $nodeTargetDir "node.exe") -Force
}

Invoke-Step "Create writable folders and helper scripts" {
  New-Item -ItemType Directory -Force -Path (Join-Path $finalDir "data") | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $finalDir "logs") | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $finalDir "reports") | Out-Null

  $stopContent = @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; foreach($id in $p){ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }; Write-Host 'XHS local tool stopped.'; pause"
'@
  Set-Content -Path (Join-Path $finalDir $stopBatName) -Value $stopContent -Encoding ASCII
}

Write-Host ""
Write-Host "Windows exe package created:"
Write-Host $finalDir
Write-Host ""
Write-Host "Main executable:"
Write-Host (Join-Path $finalDir "$appName.exe")
