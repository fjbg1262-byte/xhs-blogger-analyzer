param(
  [string]$Version = '0.3.0-beta.7',
  [string]$Python = '',
  [switch]$SkipFrontend
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($Version -notmatch '^[a-zA-Z0-9.-]+$') { throw 'Invalid version' }
if (-not $Python) { $Python = Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Python environment missing; install requirements.lock.txt into .venv first.' }
$releaseRoot = Join-Path $projectRoot 'release'
$package = Join-Path $releaseRoot "XHS-Organizer-$Version"
$buildRoot = Join-Path $projectRoot '.build'
$buildPath = Join-Path $buildRoot $Version
if (Test-Path -LiteralPath $package) { throw 'Release already exists. Use a new version; do not overwrite used delivery folders.' }
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

if (-not $SkipFrontend) {
  Push-Location (Join-Path $projectRoot 'frontend')
  try { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' } } finally { Pop-Location }
}
& $Python (Join-Path $PSScriptRoot 'release_source.py') snapshot --root $projectRoot --out (Join-Path $buildPath 'source') --version $Version
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
& $Python -m PyInstaller --noconfirm --clean --onedir --name XHS-Organizer `
  --distpath (Join-Path $buildPath 'dist') --workpath (Join-Path $buildPath 'work') --specpath $buildPath `
  --hidden-import backend.app --hidden-import openpyxl --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on `
  --hidden-import httptools --hidden-import websockets.legacy.server `
  --hidden-import sqlalchemy.sql.default_comparator --hidden-import execjs --hidden-import execjs._runtimes `
  (Join-Path $projectRoot 'desktop_entry.py')
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }

function Copy-Tree($from,$to) {
  robocopy $from $to /E /XD .git __pycache__ logs data reports author /XF .env cookies.json '*.log' '*.pyc' '*.db' /NFL /NDL /NJH /NJS | Out-Null
  if ($LASTEXITCODE -gt 7) { throw "Resource copy failed: $from" }
}
Copy-Tree (Join-Path $buildPath 'dist\XHS-Organizer') $package
Copy-Tree (Join-Path $projectRoot 'frontend\dist') (Join-Path $package 'frontend\dist')
Copy-Tree (Join-Path $projectRoot 'spider_xhs') (Join-Path $package 'spider_xhs')
Copy-Tree (Join-Path $projectRoot 'static') (Join-Path $package 'static')
Copy-Tree (Join-Path $projectRoot 'browser-extension') (Join-Path $package 'browser-extension')
foreach ($name in @('analyze_all.py','generate_reports.py')) { Copy-Item -LiteralPath (Join-Path $projectRoot $name) -Destination $package }
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\ORGANIZER_USER_GUIDE.md') -Destination (Join-Path $package 'README.md')
Copy-Item -LiteralPath (Join-Path $buildPath 'source\SOURCE_MANIFEST.json') -Destination $package
Copy-Item -LiteralPath (Join-Path $buildPath "source\source-$Version.zip") -Destination $releaseRoot
New-Item -ItemType Directory -Force -Path (Join-Path $package 'runtime\node') | Out-Null
Copy-Item -LiteralPath (Get-Command node).Source -Destination (Join-Path $package 'runtime\node\node.exe')
@{app_version=$Version;endpoint='';ingest_key=''} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $package 'telemetry_config.json') -Encoding UTF8
& (Join-Path $package 'XHS-Organizer.exe') --xhs-self-check
if ($LASTEXITCODE -ne 0) { throw 'Packaged self-check failed' }
& $Python (Join-Path $PSScriptRoot 'release_source.py') scan --out $package
if ($LASTEXITCODE -ne 0) { throw 'Package contains runtime data' }
& $Python (Join-Path $PSScriptRoot 'zip_release.py') --root $package --out "$package.zip"
if ($LASTEXITCODE -ne 0) { throw 'Zip creation failed' }
Write-Output "Package ready: $package.zip"
