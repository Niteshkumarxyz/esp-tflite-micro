# Read-only evidence collector for the "Same Model, Different Robot" chapter.
# Run from: examples\person_detection
# This script DOES NOT build, modify source files, or flash the ESP32.
$ErrorActionPreference = "Continue"

$projectDir = (Get-Location).Path
$required = @(".\sdkconfig", ".\build\person_detection.bin", ".\main\esp_cli.c")
foreach ($p in $required) {
    if (!(Test-Path $p)) {
        throw "Required path not found: $p. Open PowerShell in examples\person_detection and rerun."
    }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $projectDir ("chapter_evidence\build_metadata_" + $stamp)
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

function Save-Output {
    param(
        [string]$FileName,
        [string]$Label,
        [object[]]$Lines,
        [int]$ExitCode = 0
    )
    $target = Join-Path $outDir $FileName
    @(
        "LABEL: $Label"
        "CAPTURED_AT: $((Get-Date).ToString('o'))"
        "EXIT_CODE: $ExitCode"
        ""
        ($Lines | ForEach-Object { [string]$_ })
    ) | Set-Content -LiteralPath $target -Encoding UTF8
    Write-Host ("Saved " + $target)
}

# Capture repository identity and working-tree state.
$repoRootLines = & git -C $projectDir rev-parse --show-toplevel 2>&1
$repoRootExit = $LASTEXITCODE
Save-Output "git_root.txt" "git rev-parse --show-toplevel" $repoRootLines $repoRootExit

$repoRoot = ($repoRootLines | Select-Object -First 1).ToString().Trim()
if ($repoRootExit -eq 0 -and (Test-Path $repoRoot)) {
    $head = & git -C $repoRoot rev-parse HEAD 2>&1
    $exit = $LASTEXITCODE
    Save-Output "git_head.txt" "git rev-parse HEAD" $head $exit

    $lastCommit = & git -C $repoRoot log -1 --format="%H%n%ci%n%s" 2>&1
    $exit = $LASTEXITCODE
    Save-Output "git_last_commit.txt" "git log -1 --format" $lastCommit $exit

    $status = & git -C $repoRoot status --short 2>&1
    $exit = $LASTEXITCODE
    Save-Output "git_status_short.txt" "git status --short" $status $exit

    $submodules = & git -C $repoRoot submodule status --recursive 2>&1
    $exit = $LASTEXITCODE
    Save-Output "git_submodules_recursive.txt" "git submodule status --recursive" $submodules $exit
}

# Capture tool versions; a failing command is retained as evidence instead of silently omitted.
$pythonVersion = & python --version 2>&1
$exit = $LASTEXITCODE
Save-Output "python_version.txt" "python --version" $pythonVersion $exit

$idfVersion = & idf.py --version 2>&1
$exit = $LASTEXITCODE
Save-Output "idf_py_version.txt" "idf.py --version (failure/help text, if unsupported, is retained)" $idfVersion $exit

$idfSize = & idf.py size 2>&1
$exit = $LASTEXITCODE
Save-Output "idf_py_size.txt" "idf.py size (uses current build artifacts; does not flash)" $idfSize $exit

$idfSizeComponents = & idf.py size-components 2>&1
$exit = $LASTEXITCODE
Save-Output "idf_py_size_components.txt" "idf.py size-components (uses current build artifacts; does not flash)" $idfSizeComponents $exit

# Preserve the kernel-related config lines verbatim from both source and generated config.
$configLines = @()
$configFiles = @(".\sdkconfig", ".\build\config\sdkconfig.h")
foreach ($cf in $configFiles) {
    if (Test-Path $cf) {
        $configLines += "=== $cf ==="
        $configLines += (Select-String -Path $cf -Pattern "CONFIG_NN_OPTIMIZED|CONFIG_NN_OPTIMIZATIONS|CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN|CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ|CONFIG_ESP_DEFAULT_CPU_FREQ" | ForEach-Object { $_.Line })
    }
}
Save-Output "kernel_and_clock_config.txt" "Selected source and generated configuration lines" $configLines 0

# Hash the artifacts and source files that identify the captured firmware/build.
$hashTargets = @(
    ".\sdkconfig",
    ".\build\config\sdkconfig.h",
    ".\build\person_detection.bin",
    ".\build\person_detection.elf",
    ".\build\build.ninja",
    ".\main\CMakeLists.txt",
    ".\main\esp_cli.c",
    ".\main\main_functions.cc",
    ".\sdkconfig.R2A_backup_20261022",
    ".\main\CMakeLists.txt.before_drift_20261022",
    ".\main\esp_cli.c.before_drift_20261022",
    ".\main\esp_cli.c.before_drift600_20261022"
)
$hashRows = foreach ($item in $hashTargets) {
    if (Test-Path $item) {
        $h = Get-FileHash -LiteralPath $item -Algorithm SHA256
        [pscustomobject]@{
            RelativePath = $item
            LengthBytes = (Get-Item -LiteralPath $item).Length
            SHA256 = $h.Hash
        }
    }
}
$hashRows | Export-Csv -LiteralPath (Join-Path $outDir "artifact_sha256.csv") -NoTypeInformation -Encoding UTF8

$meta = @"
ESP32 build metadata capture
Captured at: $((Get-Date).ToString('o'))
Project directory: $projectDir
Git root candidate: $repoRoot
Purpose: preserve exact version/build/cost evidence for chapter Table 3 and RQ3.
Scope: read-only; this script does not change source files, build the firmware, or flash the board.
Important: record the exact binary SHA-256 with every reported measurement; different ELF/BIN builds must not be pooled.
"@
$meta | Set-Content -LiteralPath (Join-Path $outDir "README.txt") -Encoding UTF8

# Hash the metadata files themselves after capture.
$capturedFiles = Get-ChildItem -LiteralPath $outDir -File |
    Where-Object { $_.Name -ne "metadata_package_sha256.csv" }
$capturedFiles | ForEach-Object {
    $h = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    [pscustomobject]@{
        File = $_.Name
        LengthBytes = $_.Length
        SHA256 = $h.Hash
    }
} | Export-Csv -LiteralPath (Join-Path $outDir "metadata_package_sha256.csv") -NoTypeInformation -Encoding UTF8

$zipPath = "$outDir.zip"
Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "BUILD METADATA CAPTURE COMPLETE" -ForegroundColor Green
Write-Host "Folder: $outDir"
Write-Host "ZIP:    $zipPath"
Write-Host "Please upload the ZIP here. Do not paste passwords/tokens; the script does not collect Git remote URLs."
Write-Host "No firmware was built or flashed."
