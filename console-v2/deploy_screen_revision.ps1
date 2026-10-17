$ErrorActionPreference = 'Stop'
$petStage = $PSScriptRoot
$petTarget = 'C:\Users\meursault\Desktop\desktop-pet'
if ((Resolve-Path -LiteralPath $petTarget).Path -ne $petTarget -or -not (Test-Path -LiteralPath (Join-Path $petTarget 'pet_backend.py'))) { throw 'Unexpected target directory' }
if (Get-Process -Name 'xiaoju-console' -ErrorAction SilentlyContinue) { throw 'Pet is still running; deployment stopped' }
$petRelease = Join-Path $petStage 'frontend\src-tauri\target\release\xiaoju-console.exe'
if (-not (Test-Path -LiteralPath $petRelease)) { throw 'Release EXE missing' }
$petFiles = @('action_player.py','test_action_player.py','frontend\src\actionTimeline.ts','frontend\src\components\ActionLibrary.tsx','frontend\tests\actionTimeline.test.mjs','assets\actions\catalog.json','frontend\public\actions\catalog.json','qa\actions\screen.jpg','qa\actions\screen.gif','qa\actions\screen-operating.gif')
$petFolders = @('assets\actions\screen','frontend\public\actions\screen')
$petBackup = Join-Path $petStage ('backup-screen-deploy-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $petBackup | Out-Null
foreach ($petRelative in ($petFiles + $petFolders + @('app\xiaoju-console.exe'))) {
    $petExisting = Join-Path $petTarget $petRelative
    if (Test-Path -LiteralPath $petExisting) {
        $petSaved = Join-Path $petBackup $petRelative
        New-Item -ItemType Directory -Path (Split-Path -Parent $petSaved) -Force | Out-Null
        Copy-Item -LiteralPath $petExisting -Destination $petSaved -Recurse
    }
}
foreach ($petRelative in $petFiles) {
    $petDestination = Join-Path $petTarget $petRelative
    New-Item -ItemType Directory -Path (Split-Path -Parent $petDestination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $petStage $petRelative) -Destination $petDestination -Force
}
foreach ($petRelative in $petFolders) {
    $petDestination = Join-Path $petTarget $petRelative
    New-Item -ItemType Directory -Path $petDestination -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $petStage $petRelative) -File | Copy-Item -Destination $petDestination -Force
}
Copy-Item -LiteralPath $petRelease -Destination (Join-Path $petTarget 'app\xiaoju-console.exe') -Force
foreach ($petRelative in $petFiles) {
    if ((Get-FileHash -LiteralPath (Join-Path $petStage $petRelative)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $petTarget $petRelative)).Hash) { throw "Hash mismatch: $petRelative" }
}
foreach ($petRelative in $petFolders) {
    foreach ($petItem in (Get-ChildItem -LiteralPath (Join-Path $petStage $petRelative) -File)) {
        if ((Get-FileHash -LiteralPath $petItem.FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path (Join-Path $petTarget $petRelative) $petItem.Name)).Hash) { throw "Asset hash mismatch: $($petItem.Name)" }
    }
}
if ((Get-FileHash -LiteralPath $petRelease).Hash -ne (Get-FileHash -LiteralPath (Join-Path $petTarget 'app\xiaoju-console.exe')).Hash) { throw 'EXE hash mismatch' }
Write-Host "Deployed screen revision 2. Verified hashes. Backup: $petBackup"
