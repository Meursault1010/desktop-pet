param([string]$Version='v1.1.1',[string]$Candidate=(Join-Path $PSScriptRoot 'releases/electron/yuki-win32-x64-release-candidate-v2/yuki-win32-x64'))
$ErrorActionPreference='Stop'
$tag=$Version.TrimStart('v')
$output=Join-Path $PSScriptRoot "releases/electron/release-assets-v$tag"
$modelName='Qwen3.8-4B-Q4_K_M.gguf'
$modelSource=Join-Path $PSScriptRoot "local-model/qwen/$modelName"
$modelTemp=Join-Path $output $modelName
$chunkSize=1500000000L
$archive=Join-Path $output "yuki-win32-x64-$Version.tar.gz"
if(-not(Test-Path (Join-Path $Candidate 'yuki.exe'))){throw "Candidate not found: $Candidate"}
if(-not(Test-Path $modelSource)){throw "Local model not found: $modelSource"}
New-Item -ItemType Directory -Path $output -Force | Out-Null
if(Test-Path $modelTemp){Remove-Item -LiteralPath $modelTemp -Force}
Copy-Item -LiteralPath $modelSource -Destination $modelTemp
$bundledModel=Join-Path $Candidate "resources/local-model/qwen/$modelName"
if(Test-Path $bundledModel){Remove-Item -LiteralPath $bundledModel -Force}
$installer=Join-Path $Candidate 'install-yuki.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install-yuki.ps1') -Destination $installer -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'local-model/qwen/README.md') -Destination (Join-Path $Candidate 'MODEL-NOTICE.txt') -Force
$modelHash=(Get-FileHash -LiteralPath $modelTemp -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest=[ordered]@{version=$Version;modelFile=$modelName;modelSha256=$modelHash}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Candidate 'release-manifest.json') -Encoding ascii
if(Test-Path $archive){Remove-Item -LiteralPath $archive -Force}
$stale=Get-ChildItem -LiteralPath $output -File | Where-Object {$_.Name -like "yuki-win32-x64-$Version.tar.gz.part*" -or $_.Name -like "yuki-model-$Version.part*"}
if($stale){$stale|Remove-Item -Force}
& tar.exe -czf $archive -C (Split-Path -Parent $Candidate) (Split-Path -Leaf $Candidate)
if($LASTEXITCODE -ne 0){throw "Application archive creation failed ($LASTEXITCODE)"}
$partNames=@("yuki-model-$Version.part01","yuki-model-$Version.part02")
foreach($name in $partNames){$old=Join-Path $output $name;if(Test-Path $old){Remove-Item -LiteralPath $old -Force}}
$source=[IO.File]::OpenRead($modelTemp);$buffer=New-Object byte[] (8MB);$part=0
try{
    while($source.Position -lt $source.Length){
        $part++;if($part -gt 2){throw 'The local model exceeds the two-part release plan.'}
        $target=Join-Path $output $partNames[$part-1];$dest=[IO.File]::Create($target);$left=$chunkSize
        try{while($left -gt 0 -and ($read=$source.Read($buffer,0,[int][Math]::Min($buffer.Length,$left))) -gt 0){$dest.Write($buffer,0,$read);$left-=$read}}finally{$dest.Dispose()}
    }
}finally{$source.Dispose()}
if($part -ne 2){throw "Expected two model parts, got $part."}
$releaseFiles=@($archive)
foreach($name in $partNames){$releaseFiles+=Join-Path $output $name}
foreach($path in $releaseFiles){
    if((Get-Item -LiteralPath $path).Length -ge 2147483648L){throw "Release file exceeds GitHub's per-file limit: $path"}
}
Remove-Item -LiteralPath $modelTemp -Force
Write-Output "Three release files ready: $output"
