param(
  [string]$Version = "test",
  [string]$SourceVersion = "windows",
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$releaseDir = Join-Path $root "release"
$sourceDir = Join-Path $releaseDir "xhs-blogger-analyzer-$SourceVersion"
$stageRoot = Join-Path $releaseDir "windows-release-stage"

function Utf8Text($Base64) {
  return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($Base64))
}

$packageBaseName = Utf8Text "WEhT5Y2a5Li75YiG5p6Q5Yqp5omLLVdpbmRvd3PmtYvor5XniYg="
$appExeName = Utf8Text "WEhT5YiG5p6Q5Yqp5omLLmV4ZQ=="
$stopBatName = Utf8Text "5YWz6Zet5pys5Zyw5bel5YW3LmJhdA=="
$guideHtmlName = Utf8Text "5L2/55So6K+05piOLmh0bWw="
$firstReadmeName = Utf8Text "UkVBRE1FLeWFiOeci+aIkS50eHQ="
$releaseNotesName = Utf8Text "54mI5pys6K+05piOLnR4dA=="

if ($Version -and $Version -ne "test") {
  $zipName = "$packageBaseName-$Version.zip"
} else {
  $zipName = "$packageBaseName.zip"
}

$packageDir = Join-Path $stageRoot $packageBaseName
$zipPath = Join-Path $releaseDir $zipName

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

function Write-Utf8File($Path, $Content) {
  Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Assert-Exists($RelativePath) {
  $path = Join-Path $packageDir $RelativePath
  if (-not (Test-Path $path)) {
    throw "Release package is missing required file: $RelativePath"
  }
}

function Assert-NotExists($RelativePath) {
  $path = Join-Path $packageDir $RelativePath
  if (Test-Path $path) {
    throw "Release package contains forbidden runtime data: $RelativePath"
  }
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

if (-not $SkipBuild) {
  & (Join-Path $PSScriptRoot "build_windows_exe.ps1") -Version $SourceVersion
  if ($LASTEXITCODE -ne 0) {
    throw "Windows exe build failed"
  }
}

if (-not (Test-Path $sourceDir)) {
  throw "Windows exe package was not found: $sourceDir"
}

Remove-SafeDir $stageRoot $releaseDir
if (Test-Path $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

$excludeDirs = @(
  ".git",
  "__pycache__",
  "data",
  "logs",
  "reports",
  "author"
)

$excludeFiles = @(
  ".env",
  "cookies.json",
  "app.db",
  "app.db-journal",
  "database.db",
  "llm_config.json",
  "*.log",
  "*.err.log",
  "*.pyc",
  "*.tar.gz"
)

Copy-Tree $sourceDir $packageDir $excludeDirs $excludeFiles
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $packageDir "README.md") -Force
Copy-Tree (Join-Path $root "docs") (Join-Path $packageDir "docs") @("__pycache__", ".git") @("*.log", "*.pyc")

New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "reports") | Out-Null

$guideTemplate = Join-Path $root "docs\PACKAGED_USER_GUIDE.html"
if (-not (Test-Path $guideTemplate)) {
  throw "Missing packaged user guide template: $guideTemplate"
}
Copy-Item -LiteralPath $guideTemplate -Destination (Join-Path $packageDir $guideHtmlName) -Force

$commit = "unknown"
try {
  $commit = (git -C $root rev-parse --short HEAD).Trim()
} catch {
  $commit = "unknown"
}
$builtAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$firstReadmeTemplate = Join-Path $root "docs\PACKAGED_README_FIRST.txt"
$releaseNotesTemplate = Join-Path $root "docs\PACKAGED_RELEASE_NOTES.txt"
if (-not (Test-Path $firstReadmeTemplate)) {
  throw "Missing first readme template: $firstReadmeTemplate"
}
if (-not (Test-Path $releaseNotesTemplate)) {
  throw "Missing release notes template: $releaseNotesTemplate"
}
Copy-Item -LiteralPath $firstReadmeTemplate -Destination (Join-Path $packageDir $firstReadmeName) -Force
Copy-Item -LiteralPath $releaseNotesTemplate -Destination (Join-Path $packageDir $releaseNotesName) -Force

$buildInfo = @(
  "Version: $Version",
  "BuiltAt: $builtAt",
  "Commit: $commit",
  "Package: $zipName"
) -join "`n"
Write-Utf8File (Join-Path $packageDir "BUILD_INFO.txt") $buildInfo

Assert-Exists $appExeName
Assert-Exists $stopBatName
Assert-Exists "browser-extension\manifest.json"
Assert-Exists "frontend\dist\index.html"
Assert-Exists "runtime\node\node.exe"
Assert-Exists "docs\images\load-unpacked.png"
Assert-Exists $guideHtmlName
Assert-Exists $firstReadmeName
Assert-Exists $releaseNotesName

Assert-NotExists "data\app.db"
Assert-NotExists "data\tasks"
Assert-NotExists "cookies.json"
Assert-NotExists ".env"
Assert-NotExists "logs\backend.log"
Assert-NotExists "reports\task_1"

$forbidden = Get-ChildItem -LiteralPath $packageDir -Recurse -File -Force |
  Where-Object {
    $_.Name -in @(".env", "cookies.json", "app.db", "database.db", "llm_config.json") -or
    $_.Extension -in @(".pyc", ".log")
  }
if ($forbidden) {
  $list = ($forbidden | Select-Object -First 20 | ForEach-Object { $_.FullName }) -join "`n"
  throw "Release package contains forbidden files:`n$list"
}

$checksumPath = Join-Path $packageDir "checksums.sha256"
$hashRows = Get-ChildItem -LiteralPath $packageDir -Recurse -File -Force |
  Where-Object { $_.FullName -ne $checksumPath } |
  Sort-Object FullName |
  ForEach-Object {
    $relative = $_.FullName.Substring($packageDir.Length).TrimStart("\")
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
    "$($hash.Hash.ToLower())  $relative"
  }
Write-Utf8File $checksumPath ($hashRows -join "`n")

Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force

if (-not (Test-Path $zipPath)) {
  throw "Zip file was not created: $zipPath"
}

$zipInfo = Get-Item -LiteralPath $zipPath
Write-Host ""
Write-Host "Windows release zip created:"
Write-Host $zipInfo.FullName
Write-Host ("Size: {0:N1} MB" -f ($zipInfo.Length / 1MB))
Write-Host ""
Write-Host "Before sharing, unzip it once on a clean Windows machine and follow the packaged HTML guide."
