$ErrorActionPreference='Stop'
$petStage=$PSScriptRoot
$petTarget='C:\Users\meursault\Desktop\desktop-pet'
if ((Resolve-Path -LiteralPath $petTarget).Path -ne $petTarget -or -not (Test-Path -LiteralPath (Join-Path $petTarget 'pet_backend.py'))) { throw 'Unexpected deployment directory' }
if (Get-Process -Name 'xiaoju-console' -ErrorAction SilentlyContinue) { throw 'Please completely exit XiaoJu before deploying' }
$petFiles=@('pet.py','main.py','pet_backend.py','desktop_icons.py','icon_sleep.py','test_icon_sleep.py','test_ipc.py','ICON_SLEEP.md','audit_desktop_icons.py','qa_icon_sleep.py','frontend\src\App.tsx','frontend\src\bridge.ts','frontend\src\usePetController.ts','frontend\src\components\IconSleep.tsx','frontend\src\components\IconSleep.css','frontend\src-tauri\src\main.rs')
$petMappings=@{}
foreach($petRelative in $petFiles){$petMappings[$petRelative]=$petRelative}
$petMappings['app\xiaoju-console.exe']='frontend\src-tauri\target\release\xiaoju-console.exe'
foreach($petFolder in @('assets\icon-sleep','action-work\icon-sleep','qa\icon-sleep')){
    foreach($petItem in (Get-ChildItem -LiteralPath (Join-Path $petStage $petFolder) -File)){
        $petRelative=Join-Path $petFolder $petItem.Name
        $petMappings[$petRelative]=$petRelative
    }
}
foreach($petRelative in $petMappings.Values){if(-not(Test-Path -LiteralPath (Join-Path $petStage $petRelative))){throw "Missing source: $petRelative"}}
$petBackup=Join-Path $petStage ('backup-icon-sleep-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $petBackup | Out-Null
foreach($petRelative in $petMappings.Keys){
    $petExisting=Join-Path $petTarget $petRelative
    if(Test-Path -LiteralPath $petExisting){
        $petSaved=Join-Path $petBackup $petRelative
        New-Item -ItemType Directory -Path (Split-Path -Parent $petSaved) -Force | Out-Null
        Copy-Item -LiteralPath $petExisting -Destination $petSaved
    }
}
foreach($petRelative in $petMappings.Keys){
    $petDestination=Join-Path $petTarget $petRelative
    New-Item -ItemType Directory -Path (Split-Path -Parent $petDestination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $petStage $petMappings[$petRelative]) -Destination $petDestination -Force
    if((Get-FileHash -LiteralPath $petDestination).Hash -ne (Get-FileHash -LiteralPath (Join-Path $petStage $petMappings[$petRelative])).Hash){throw "Hash mismatch: $petRelative"}
}
Write-Host "Icon sleep deployed; all hashes verified. Backup: $petBackup"
