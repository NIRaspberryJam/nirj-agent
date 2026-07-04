param(
    [string]$InstallDir = "$env:ProgramData\nirj",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

$repoDir = Join-Path $InstallDir "agent-repo"
$venvDir = Join-Path $InstallDir "agent-venv"
$python = Join-Path $venvDir "Scripts\python.exe"
$agent = Join-Path $venvDir "Scripts\nirj-agent.exe"
$logDir = Join-Path $InstallDir "logs"
$logFile = Join-Path $logDir "agent.log"

$env:NIRJ_AGENT_INSTALL_DIR = $InstallDir
$env:GIT_TERMINAL_PROMPT = "0"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

function Invoke-Native {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $ArgumentList"
    }
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$transcribing = $false
try {
    Start-Transcript -Path $logFile -Append | Out-Null
    $transcribing = $true
}
catch {
    Write-Warning "Unable to start transcript at ${logFile}: $_"
}

try {
    Invoke-Native -FilePath git -ArgumentList @(
        "-C", $repoDir, "fetch", "origin", $Branch
    )
    Invoke-Native -FilePath git -ArgumentList @(
        "-C", $repoDir, "checkout", $Branch
    )
    Invoke-Native -FilePath git -ArgumentList @(
        "-C", $repoDir, "merge", "--ff-only", "origin/$Branch"
    )
    Invoke-Native -FilePath $python -ArgumentList @(
        "-m", "pip", "install", "--upgrade", $repoDir
    )

    & $agent up
    $agentExitCode = $LASTEXITCODE
}
finally {
    if ($transcribing) {
        Stop-Transcript | Out-Null
    }
}

exit $agentExitCode
