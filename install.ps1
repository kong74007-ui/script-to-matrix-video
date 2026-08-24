[CmdletBinding()]
param(
    [string]$DestinationRoot = (Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex\skills'),
    [switch]$Force,
    [switch]$SkipPythonDependencies
)

$ErrorActionPreference = 'Stop'

$sourceSkill = Join-Path $PSScriptRoot 'script-to-matrix-video'
$sourceEntry = Join-Path $sourceSkill 'SKILL.md'
if (-not (Test-Path -LiteralPath $sourceEntry -PathType Leaf)) {
    throw "Skill files are incomplete: $sourceEntry was not found. Extract the complete archive before installing."
}

$catalogPath = Join-Path $sourceSkill 'assets\templates\catalog.json'
$fontRoot = Join-Path $sourceSkill 'assets\fonts'
$fontSourcesPath = Join-Path $fontRoot 'sources.json'
foreach ($requiredPath in @($catalogPath, $fontSourcesPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Skill v1.7 runtime files are incomplete: $requiredPath was not found."
    }
}

$catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json
$templateIds = @($catalog.templates | ForEach-Object { [string]$_.id })
if ($catalog.version -ne 1 -or $templateIds.Count -ne 12 -or @($templateIds | Sort-Object -Unique).Count -ne 12) {
    throw 'Template catalog must be version 1 with exactly 12 unique template IDs.'
}

$fontSources = Get-Content -LiteralPath $fontSourcesPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($fontSources.fonts).Count -ne 4) {
    throw 'Font source manifest must contain exactly four bundled font families.'
}
foreach ($font in $fontSources.fonts) {
    $fontName = [string]$font.file
    $licenseName = [string]$font.license_file
    if ([IO.Path]::GetFileName($fontName) -ne $fontName -or [IO.Path]::GetFileName($licenseName) -ne $licenseName) {
        throw 'Font source manifest contains an unsafe file path.'
    }
    $fontPath = Join-Path $fontRoot $fontName
    $licensePath = Join-Path $fontRoot $licenseName
    if (-not (Test-Path -LiteralPath $fontPath -PathType Leaf) -or -not (Test-Path -LiteralPath $licensePath -PathType Leaf)) {
        throw "Bundled font or license is missing: $fontName"
    }
    $actualHash = (Get-FileHash -LiteralPath $fontPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne ([string]$font.sha256).ToLowerInvariant()) {
        throw "Bundled font hash mismatch: $fontName"
    }
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw 'Python 3.10 or newer is required. Install Python, reopen PowerShell, and run this installer again.'
}

New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
$targetSkill = Join-Path $DestinationRoot 'script-to-matrix-video'

if (Test-Path -LiteralPath $targetSkill) {
    if (-not $Force) {
        throw "The Skill is already installed at $targetSkill. Re-run with -Force to keep a timestamped backup and replace it."
    }
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupSkill = "$targetSkill.backup-$timestamp"
    Move-Item -LiteralPath $targetSkill -Destination $backupSkill
    Write-Host "Existing Skill moved to $backupSkill"
}

Copy-Item -LiteralPath $sourceSkill -Destination $targetSkill -Recurse
Write-Host "Skill copied to $targetSkill"

if (-not $SkipPythonDependencies) {
    & $pythonCommand.Source -m pip install -r (Join-Path $targetSkill 'requirements.txt')
    if ($LASTEXITCODE -ne 0) {
        throw 'Python dependency installation failed.'
    }
}

& $pythonCommand.Source (Join-Path $targetSkill 'scripts\check_environment.py')
$checkExitCode = $LASTEXITCODE

if ($checkExitCode -ne 0) {
    Write-Warning 'The Skill was copied, but the machine is missing a required runtime dependency. Follow 安装使用说明.md and run the checker again.'
    exit $checkExitCode
}

if (-not $env:DASHSCOPE_API_KEY) {
    Write-Warning 'DASHSCOPE_API_KEY is not configured. No-narration videos work now; Alibaba narration will require the key.'
}

Write-Host ''
Write-Host 'Installation complete. Restart Codex, then invoke $script-to-matrix-video.'
