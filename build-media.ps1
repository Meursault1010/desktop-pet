$ErrorActionPreference='Stop'
$destination=Join-Path $PSScriptRoot '.electron-build/media'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$framework=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319'
& (Join-Path $framework 'csc.exe') /nologo /target:exe /platform:x64 /optimize+ ("/out:"+(Join-Path $destination 'yuki-media.exe')) /reference:System.Web.Extensions.dll ("/reference:"+(Join-Path $framework 'WPF/UIAutomationClient.dll')) ("/reference:"+(Join-Path $framework 'WPF/UIAutomationTypes.dll')) ("/reference:"+(Join-Path $framework 'WPF/WindowsBase.dll')) (Join-Path $PSScriptRoot 'tools/media/NetEaseMedia.cs')
if($LASTEXITCODE){throw 'NetEase media helper build failed'}
