param(
    [string]$UpdatedSince = ""
)

$ErrorActionPreference = "Stop"

function Assert-ExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        Write-Error "FAILED at step: $Step (exit code $LASTEXITCODE)"
        Stop-Transcript
        exit $LASTEXITCODE
    }
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logDir "refresh-$timestamp.log"

Start-Transcript -Path $logFile

Write-Host "Running CT.gov ICU refresh..."

if ($UpdatedSince) {
    python "$root\fetch_ctgov_icu_placebo.py" --updated-since $UpdatedSince
    Assert-ExitCode "fetch broad (updated-since)"
    python "$root\fetch_ctgov_icu_placebo.py" --query icu_rct_placebo --updated-since $UpdatedSince
    Assert-ExitCode "fetch placebo (updated-since)"
} else {
    python "$root\fetch_ctgov_icu_placebo.py"
    Assert-ExitCode "fetch broad"
    python "$root\fetch_ctgov_icu_placebo.py" --query icu_rct_placebo
    Assert-ExitCode "fetch placebo"
}

python "$root\build_living_map.py"
Assert-ExitCode "build living map (broad)"
python "$root\build_living_map.py" --studies "$root\output\icu_rct_placebo_studies.csv" --hemo "$root\output\icu_rct_placebo_hemodynamic_mentions.csv" --label placebo
Assert-ExitCode "build living map (placebo)"

Copy-Item -Path "$root\output\icu_rct_broad_arms.csv" -Destination "$root\dashboard\data\icu_rct_broad_arms.csv" -Force
Copy-Item -Path "$root\output\icu_rct_placebo_arms.csv" -Destination "$root\dashboard\data\icu_rct_placebo_arms.csv" -Force

Write-Host "Writing output manifest..."
$manifestPath = Join-Path $root "output\manifest.json"
$files = Get-ChildItem -Path (Join-Path $root "output") -File | Where-Object { $_.Extension -in ".csv",".json",".parquet" -and $_.Name -ne "manifest.json" }
$manifest = $files | ForEach-Object {
    [pscustomobject]@{
        path = $_.FullName
        sha256 = (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash
        size_bytes = $_.Length
        modified_utc = $_.LastWriteTimeUtc.ToString("o")
    }
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -Path $manifestPath

Write-Host "Refresh complete."

Stop-Transcript
