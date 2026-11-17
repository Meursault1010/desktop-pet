param([string]$Repository='Meursault1010/desktop-pet',[string]$AssetsPath='', [string]$InstallRoot='', [switch]$NoLaunch)
$ErrorActionPreference='Stop'
$release=$null
if($AssetsPath){
    $assets=@(Get-ChildItem -LiteralPath $AssetsPath -Filter 'yuki-win32-x64-v*.tar.gz.part*' | Sort-Object Name)
    $match=[regex]::Match(($assets | Select-Object -First 1 -ExpandProperty Name),'yuki-win32-x64-(v[^.]+(?:\.[^.]+){2})\.tar\.gz\.part')
    if($match.Success){$tag=$match.Groups[1].Value}
    $manifest=Get-Item -LiteralPath (Join-Path $AssetsPath 'sha256sums.txt') -ErrorAction SilentlyContinue
}else{
    $release=Invoke-RestMethod -Headers @{Accept='application/vnd.github+json'} -Uri "https://api.github.com/repos/$Repository/releases/latest"
    $tag=[string]$release.tag_name
    $prefix="yuki-win32-x64-$tag.tar.gz.part"
    $assets=@($release.assets | Where-Object name -Like "$prefix*") | Sort-Object name
    $manifest=$release.assets | Where-Object name -eq 'sha256sums.txt' | Select-Object -First 1
}
if(-not $tag){throw 'No Yuki release files were found.'}
if($assets.Count -lt 2 -or -not $manifest){throw "Release $tag is missing installation files."}
$tempRoot=Join-Path $env:TEMP ("yuki-install-"+[guid]::NewGuid().ToString('N'))
if(-not $InstallRoot){$InstallRoot=Join-Path $env:LOCALAPPDATA "Programs\Yuki\$tag"}
if(Test-Path $installRoot){throw "This version is already installed at $installRoot"}
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
try{
    $sumPath=Join-Path $tempRoot 'sha256sums.txt'
    if($AssetsPath){Copy-Item -LiteralPath $manifest.FullName -Destination $sumPath}else{Invoke-WebRequest -Uri $manifest.browser_download_url -OutFile $sumPath}
    $expected=@{}
    foreach($line in Get-Content -LiteralPath $sumPath){if($line -match '^([a-fA-F0-9]{64}) \*(.+)$'){$expected[$Matches[2]]=$Matches[1].ToLowerInvariant()}}
    $archive=Join-Path $tempRoot "yuki-win32-x64-$tag.tar.gz"
    $output=[IO.File]::Create($archive)
    try{
        foreach($asset in $assets){
            if(-not $expected.ContainsKey($asset.name)){throw "Missing checksum for $($asset.name)"}
            $part=Join-Path $tempRoot $asset.name
            if($AssetsPath){Copy-Item -LiteralPath $asset.FullName -Destination $part}else{Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $part}
            $actual=(Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant()
            if($actual -ne $expected[$asset.name]){throw "Checksum mismatch: $($asset.name)"}
            $partStream=[IO.File]::OpenRead($part)
            try{$partStream.CopyTo($output)}finally{$partStream.Dispose()}
            Remove-Item -LiteralPath $part -Force
        }
    }finally{$output.Dispose()}
    $archiveName=Split-Path -Leaf $archive
    if(-not $expected.ContainsKey($archiveName) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected[$archiveName]){throw 'Portable archive checksum mismatch.'}
    $listing=& tar.exe -tzf $archive
    if($LASTEXITCODE -ne 0 -or @($listing | Where-Object {$_ -match '^(?:/|[a-zA-Z]:|\.\.(?:/|\\)|[^/]+/\.\.(?:/|\\))'}).Count){throw 'Portable archive contains an unsafe path.'}
    $extract=Join-Path $tempRoot 'extract';New-Item -ItemType Directory -Path $extract | Out-Null
    & tar.exe -xzf $archive -C $extract
    if($LASTEXITCODE -ne 0){throw 'Portable files could not be extracted.'}
    $application=Join-Path $extract 'yuki-win32-x64'
    if(-not(Test-Path (Join-Path $application 'yuki.exe'))){throw 'Portable archive does not contain yuki.exe.'}
    New-Item -ItemType Directory -Path (Split-Path -Parent $installRoot) -Force | Out-Null
    Move-Item -LiteralPath $application -Destination $installRoot
    $shortcut=$null
    if(-not $NoLaunch){
        try{$shell=New-Object -ComObject WScript.Shell;$shortcut=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Yuki 桌面宠物.lnk'));$shortcut.TargetPath=Join-Path $installRoot 'yuki.exe';$shortcut.WorkingDirectory=$installRoot;$shortcut.IconLocation=Join-Path $installRoot 'yuki.exe';$shortcut.Save()}catch{}
        Start-Process -FilePath (Join-Path $installRoot 'yuki.exe') -WorkingDirectory $installRoot
    }
    Write-Output "Yuki $tag installed at $installRoot"
}finally{
    $tempFull=[IO.Path]::GetFullPath($tempRoot);$tempBase=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if($tempFull.StartsWith($tempBase,[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $tempFull -Recurse -Force -ErrorAction SilentlyContinue}
}
