$ErrorActionPreference='Stop'
$destination=Join-Path $PSScriptRoot '.electron-build/selection'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$compiler=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$assembly=Join-Path $env:WINDIR 'Microsoft.NET/assembly/GAC_MSIL'
$uia=(Get-ChildItem (Join-Path $assembly 'UIAutomationClient') -Recurse -Filter UIAutomationClient.dll | Select-Object -First 1).FullName
$types=(Get-ChildItem (Join-Path $assembly 'UIAutomationTypes') -Recurse -Filter UIAutomationTypes.dll | Select-Object -First 1).FullName
$windows=(Get-ChildItem (Join-Path $assembly 'WindowsBase') -Recurse -Filter WindowsBase.dll | Select-Object -First 1).FullName
& $compiler /nologo /target:exe /platform:x64 /optimize+ ("/out:"+(Join-Path $destination 'yuki-selection.exe')) /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll ("/reference:"+$uia) ("/reference:"+$types) ("/reference:"+$windows) (Join-Path $PSScriptRoot 'tools/selection/SelectionHelper.cs')
if($LASTEXITCODE){throw 'Windows selection helper build failed'}
