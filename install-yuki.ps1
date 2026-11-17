param([string]$AssetsPath=(Get-Location).Path,[string]$InstallRoot='',[switch]$IncludeModel,[switch]$NoLaunch)
$ErrorActionPreference='Stop'
$archive=Get-ChildItem -LiteralPath $AssetsPath -Filter 'yuki-win32-x64-v*.zip' -File | Select-Object -First 1
if(-not $archive){throw 'Place the Yuki application archive beside this script.'}
$tag=[regex]::Match($archive.Name,'yuki-win32-x64-(v\d+\.\d+\.\d+)\.zip').Groups[1].Value
if(-not $tag){throw 'Could not identify the Yuki version.'}
if(-not $InstallRoot){$InstallRoot=Join-Path $env:LOCALAPPDATA "Programs\Yuki\$tag"}
if(Test-Path $InstallRoot){throw "This version is already installed at $InstallRoot"}
$tempRoot=Join-Path $env:TEMP ("yuki-install-"+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
try{
    $zip=[IO.Compression.ZipFile]::OpenRead($archive.FullName)
    try{
        foreach($entry in $zip.Entries){if($entry.FullName -match '^(?:/|[a-zA-Z]:|\.\.(?:/|\\)|[^/]+/\.\.(?:/|\\))'){throw 'The application archive contains an unsafe path.'}}
        [IO.Compression.ZipFileExtensions]::ExtractToDirectory($zip,$tempRoot)
    }finally{$zip.Dispose()}
    $application=Join-Path $tempRoot 'yuki-win32-x64'
    if(-not(Test-Path (Join-Path $application 'yuki.exe'))){throw 'The archive does not contain yuki.exe.'}
    if($IncludeModel){
        $manifest=Get-Content -LiteralPath (Join-Path $application 'release-manifest.json') -Raw | ConvertFrom-Json
        $modelPath=Join-Path $tempRoot $manifest.modelFile
        $output=[IO.File]::Create($modelPath)
        try{
            foreach($suffix in @('part01','part02')){
                $partName="yuki-model-$tag.$suffix";$part=Get-Item -LiteralPath (Join-Path $AssetsPath $partName) -ErrorAction Stop
                $stream=[IO.File]::OpenRead($part.FullName)
                try{$stream.CopyTo($output)}finally{$stream.Dispose()}
            }
        }finally{$output.Dispose()}
        $actual=(Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if($actual -ne $manifest.modelSha256){throw 'Local model checksum mismatch; keep the downloaded files and try again.'}
        $modelFolder=Join-Path $application 'resources/local-model/qwen';New-Item -ItemType Directory -Path $modelFolder -Force | Out-Null
        Move-Item -LiteralPath $modelPath -Destination (Join-Path $modelFolder $manifest.modelFile)
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'MODEL-NOTICE.txt') -Destination $modelFolder -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $InstallRoot) -Force | Out-Null
    Move-Item -LiteralPath $application -Destination $InstallRoot
    if(-not $NoLaunch){
        try{$shell=New-Object -ComObject WScript.Shell;$shortcut=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Yuki 桌面宠物.lnk'));$shortcut.TargetPath=Join-Path $InstallRoot 'yuki.exe';$shortcut.WorkingDirectory=$InstallRoot;$shortcut.IconLocation=Join-Path $InstallRoot 'yuki.exe';$shortcut.Save()}catch{}
        Start-Process -FilePath (Join-Path $InstallRoot 'yuki.exe') -WorkingDirectory $InstallRoot
    }
    Write-Output "Yuki $tag installed at $InstallRoot"
}finally{
    $tempFull=[IO.Path]::GetFullPath($tempRoot);$tempBase=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if($tempFull.StartsWith($tempBase,[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $tempFull -Recurse -Force -ErrorAction SilentlyContinue}
}
