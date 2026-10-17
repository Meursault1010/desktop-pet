$ErrorActionPreference='Stop'
$petTarget='C:\Users\meursault\Desktop\desktop-pet'
if ((Resolve-Path -LiteralPath $petTarget).Path -ne $petTarget) { throw 'Unexpected project path' }
if (Get-Process -Name 'xiaoju-console' -ErrorAction SilentlyContinue) { throw 'Please exit XiaoJu before replacing files' }
$petProcesses=Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'"
if ($petProcesses | Where-Object { $_.CommandLine -like '*desktop-pet*pet_backend*' }) { throw 'Pet backend is still running' }
$petFiles=@('icon_sleep.py','test_icon_sleep.py','ICON_SLEEP.md')
if ((Get-FileHash -LiteralPath (Join-Path $petTarget 'icon_sleep.py')).Hash -ne '7C31C73D4692A422CEB0F9047B192B02B790EFC1E3479DB7BE7110A626D78BD1') { throw 'Deployed source has changed; review before overwriting' }
foreach($petFile in $petFiles){
    if(-not(Test-Path -LiteralPath (Join-Path $PSScriptRoot $petFile))){throw "Missing source: $petFile"}
}
$petBackup=Join-Path $PSScriptRoot ('backup-sleep-visibility-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $petBackup | Out-Null
foreach($petFile in $petFiles){Copy-Item -LiteralPath (Join-Path $petTarget $petFile) -Destination (Join-Path $petBackup $petFile)}
foreach($petFile in $petFiles){
    $petSource=Join-Path $PSScriptRoot $petFile
    $petDestination=Join-Path $petTarget $petFile
    Copy-Item -LiteralPath $petSource -Destination $petDestination -Force
    if((Get-FileHash -LiteralPath $petSource).Hash -ne (Get-FileHash -LiteralPath $petDestination).Hash){throw "Hash mismatch: $petFile"}
}
Write-Output "Deployed 3 files; hashes verified. Backup: $petBackup"
