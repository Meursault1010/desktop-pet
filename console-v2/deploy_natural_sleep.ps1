$ErrorActionPreference='Stop'
$petTarget='C:\Users\meursault\Desktop\desktop-pet'
if ((Resolve-Path -LiteralPath $petTarget).Path -ne $petTarget) {throw 'Unexpected target'}
if (Get-Process -Name 'xiaoju-console' -ErrorAction SilentlyContinue) {throw 'Exit XiaoJu first'}
$petProcesses=Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'"
if($petProcesses | Where-Object {$_.CommandLine -like '*desktop-pet*pet_backend*'}){throw 'Backend still running'}
if((Get-FileHash -LiteralPath (Join-Path $petTarget 'icon_sleep.py')).Hash -ne '8CE1EF32F4CF6300EA025C18373A6B3BC3140B3986729138E058EAF3CC78E87F'){throw 'Deployed source changed'}
$petMappings=@{}
foreach($petFile in @('icon_sleep.py','test_icon_sleep.py','ICON_SLEEP.md','qa_natural_sleep.py','frontend\src\components\IconSleep.tsx')){$petMappings[$petFile]=$petFile}
$petMappings['app\xiaoju-console.exe']='frontend\src-tauri\target\release\xiaoju-console.exe'
foreach($petFolder in @('qa\icon-sleep-v2')){
    foreach($petItem in (Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot $petFolder) -File)){
        $petRelative=Join-Path $petFolder $petItem.Name
        $petMappings[$petRelative]=$petRelative
    }
}
foreach($petSource in $petMappings.Values){if(-not(Test-Path -LiteralPath (Join-Path $PSScriptRoot $petSource))){throw "Missing: $petSource"}}
$petBackup=Join-Path $PSScriptRoot ('backup-natural-sleep-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
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
    $petSource=Join-Path $PSScriptRoot $petMappings[$petRelative]
    $petDestination=Join-Path $petTarget $petRelative
    New-Item -ItemType Directory -Path (Split-Path -Parent $petDestination) -Force | Out-Null
    Copy-Item -LiteralPath $petSource -Destination $petDestination -Force
    if((Get-FileHash -LiteralPath $petSource).Hash -ne (Get-FileHash -LiteralPath $petDestination).Hash){throw "Hash mismatch: $petRelative"}
}
Write-Output "Natural sleep deployed and hashes verified. Backup: $petBackup"
