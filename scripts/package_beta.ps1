param(
  [string]$Version = "beta"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$releaseDir = Join-Path $root "release"
$stageDir = Join-Path $releaseDir "xhs-blogger-analyzer-$Version"
$zipPath = Join-Path $releaseDir "xhs-blogger-analyzer-$Version.zip"

if (Test-Path $stageDir) {
  $resolvedStage = Resolve-Path $stageDir
  if (-not $resolvedStage.Path.StartsWith((Resolve-Path $releaseDir).Path)) {
    throw "Refusing to clean unexpected path: $resolvedStage"
  }
  Remove-Item -LiteralPath $resolvedStage.Path -Recurse -Force
}

if (Test-Path $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

$files = @(
  "README.md",
  "requirements.txt",
  "package.json",
  "package-lock.json",
  ".env.example",
  "cookies.example.json",
  "analyze_all.py",
  "generate_reports.py",
  "install_windows.bat",
  "start_windows.bat"
)

foreach ($file in $files) {
  $source = Join-Path $root $file
  if (Test-Path $source) {
    Copy-Item -LiteralPath $source -Destination (Join-Path $stageDir $file) -Force
  }
}

$dirs = @(
  "backend",
  "browser-extension",
  "docs",
  "frontend",
  "scripts",
  "spider_xhs",
  "static"
)

$excludeDirs = @(
  "node_modules",
  "__pycache__",
  ".git",
  "dist",
  "release",
  "data",
  "reports",
  "repo",
  "repo_yize"
)

$excludeFiles = @(
  ".env",
  "cookies.json",
  "app.db",
  "database.db",
  "*.log",
  "*.pyc",
  "*.tar.gz"
)

foreach ($dir in $dirs) {
  $source = Join-Path $root $dir
  $dest = Join-Path $stageDir $dir
  if (Test-Path $source) {
    robocopy $source $dest /E /XD $excludeDirs /XF $excludeFiles | Out-Host
    if ($LASTEXITCODE -gt 7) {
      throw "robocopy failed for $dir with exit code $LASTEXITCODE"
    }
  }
}

New-Item -ItemType Directory -Force -Path (Join-Path $stageDir "data") | Out-Null

Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Package created:"
Write-Host $zipPath
Write-Host ""
Write-Host "Before sharing, unzip it once on a clean machine and follow docs/USER_GUIDE.md."
