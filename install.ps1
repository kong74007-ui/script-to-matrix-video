[CmdletBinding()]
param(
    [string]$DestinationRoot = (Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex\skills'),
    [switch]$Force,
    [switch]$SkipPythonDependencies
)

$ErrorActionPreference = 'Stop'

$sourceSkill = Join-Path $PSScriptRoot 'script-to-matrix-video'
$sourceEntry = Join-Path $sourceSkill 'SKILL.md'
$targetSkill = Join-Path $DestinationRoot 'script-to-matrix-video'
$isFirstInstall = -not (Test-Path -LiteralPath $targetSkill)
if (-not (Test-Path -LiteralPath $sourceEntry -PathType Leaf)) {
    throw "Skill files are incomplete: $sourceEntry was not found. Extract the complete archive before installing."
}

$catalogPath = Join-Path $sourceSkill 'assets\templates\catalog.json'
$referenceManifestPath = Join-Path $sourceSkill 'assets\templates\reference-typography-17\manifest.json'
$referenceRendererPath = Join-Path $sourceSkill 'scripts\render_reference_typography.py'
$fontRoot = Join-Path $sourceSkill 'assets\fonts'
$fontSourcesPath = Join-Path $fontRoot 'sources.json'
foreach ($requiredPath in @($catalogPath, $referenceManifestPath, $referenceRendererPath, $fontSourcesPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Skill v1.8 runtime files are incomplete: $requiredPath was not found."
    }
}

$catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json
$templateIds = @($catalog.templates | ForEach-Object { [string]$_.id })
if ($catalog.version -ne 1 -or $templateIds.Count -ne 8 -or @($templateIds | Sort-Object -Unique).Count -ne 8) {
    throw 'Standard template catalog must be version 1 with exactly 8 unique template IDs.'
}

$referenceManifest = Get-Content -LiteralPath $referenceManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$referenceTemplates = @($referenceManifest.templates)
$referenceIds = @($referenceTemplates | ForEach-Object { [string]$_.id })
if ($referenceManifest.version -ne 2 -or $referenceManifest.engine -ne 'hyperframes' -or $referenceTemplates.Count -ne 18 -or @($referenceIds | Sort-Object -Unique).Count -ne 18) {
    throw 'Reference typography manifest must be version 2 with exactly 18 unique HyperFrames template IDs.'
}
foreach ($template in $referenceTemplates) {
    if (-not ([string]$template.id).StartsWith('ref-')) {
        throw "Reference template ID must start with ref-: $($template.id)"
    }
    foreach ($exampleField in @('example_mp4', 'example_jpg')) {
        $relativeExample = [string]$template.$exampleField
        $examplePath = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $referenceManifestPath) $relativeExample))
        if (-not (Test-Path -LiteralPath $examplePath -PathType Leaf)) {
            throw "Reference template example is missing: $relativeExample"
        }
    }
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

& $pythonCommand.Source (Join-Path $sourceSkill 'scripts\check_environment.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Source Skill environment validation failed; the existing installation was not changed.'
}
& $pythonCommand.Source (Join-Path $sourceSkill 'scripts\test_template_catalog.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Source Skill catalog/font validation failed; the existing installation was not changed.'
}
& $pythonCommand.Source (Join-Path $sourceSkill 'scripts\test_material_library.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Source Skill material-library regression failed; the existing installation was not changed.'
}

if ($isFirstInstall) {
    Write-Host 'Checking the required first-run material-library connection...'
    & $pythonCommand.Source (Join-Path $sourceSkill 'scripts\material_library.py') inspect
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host 'Connect a local library:'
        Write-Host "  python `"$(Join-Path $sourceSkill 'scripts\material_library.py')`" connect --root `"D:\media\your-library`""
        Write-Host 'Or connect an SSH library with an existing SSH key/agent:'
        Write-Host "  python `"$(Join-Path $sourceSkill 'scripts\material_library.py')`" connect --host YOUR_SSH_ALIAS --user YOUR_USER --remote-root /absolute/library/path"
        throw 'First installation requires a verified personal material-library connection. Connect it, confirm inspect succeeds, then run the installer again.'
    }
}

New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null

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
