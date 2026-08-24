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
