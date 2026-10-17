param([string]$ToolchainDirectory)
$ErrorActionPreference = 'Stop'
if ($ToolchainDirectory) {
    $env:CARGO_HOME = Join-Path $ToolchainDirectory 'cargo'
    $env:RUSTUP_HOME = Join-Path $ToolchainDirectory 'rustup'
    $env:PATH = "$env:CARGO_HOME\bin;$env:PATH"
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw 'Rust is required to rebuild. Install Rust or pass -ToolchainDirectory.'
}
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE) { throw 'npm ci failed' }
    & npm.cmd run tauri -- build --no-bundle
    if ($LASTEXITCODE) { throw 'Desktop build failed' }
    $petAppDir = Join-Path $PSScriptRoot 'app'
    New-Item -ItemType Directory -Path $petAppDir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'frontend\src-tauri\target\release\xiaoju-console.exe') -Destination (Join-Path $petAppDir 'xiaoju-console.exe')
    Write-Host 'Build complete. Open start.bat to run.'
} finally { Pop-Location }
