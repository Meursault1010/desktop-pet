param([string]$Version,[string]$Candidate=(Join-Path $PSScriptRoot 'releases/electron/yuki-win32-x64-release-candidate-v2/yuki-win32-x64'))
$ErrorActionPreference='Stop'
$tag = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'VERSION') -Raw).Trim()
if ($tag -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$') {
    throw 'VERSION must be a stable version such as 1.1.2.'
}
if (-not $Version) { $Version = "v$tag" }
if ($Version -cne "v$tag") { throw "Release tag must match VERSION (v$tag)." }
$output=Join-Path $PSScriptRoot "releases/electron/release-assets-v$tag"
$modelName='Qwen3.8-4B-Q4_K_M.gguf'
$modelSource=Join-Path $PSScriptRoot "local-model/qwen/$modelName"
$chunkSize=1500000000L
$archive=Join-Path $output "yuki-win32-x64-$Version.zip"
if(-not(Test-Path (Join-Path $Candidate 'yuki.exe'))){throw "Candidate not found: $Candidate"}
$candidatePackage = Get-Content -LiteralPath (Join-Path $Candidate 'resources/app/package.json') -Raw | ConvertFrom-Json
if ($candidatePackage.version -cne $tag) {
    throw "Candidate app version ($($candidatePackage.version)) must match VERSION ($tag)."
}
$modelFile=Get-Item -LiteralPath $modelSource -ErrorAction SilentlyContinue
if(-not $modelFile){throw "Local model not found: $modelSource"}
if($modelFile.Length -le $chunkSize -or $modelFile.Length -gt 2*$chunkSize){
    throw 'The local model does not fit the two-part release plan.'
}
New-Item -ItemType Directory -Path $output -Force | Out-Null
$bundledModel=Join-Path $Candidate "resources/local-model/qwen/$modelName"
if(Test-Path $bundledModel){Remove-Item -LiteralPath $bundledModel -Force}
$installer=Join-Path $Candidate 'install-yuki.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install-yuki.ps1') -Destination $installer -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'local-model/qwen/README.md') -Destination (Join-Path $Candidate 'MODEL-NOTICE.txt') -Force
$stale=Get-ChildItem -LiteralPath $output -File | Where-Object {$_.Name -like "yuki-win32-x64-$Version.tar.gz*" -or $_.Name -like "yuki-model-$Version.part*"}
if($stale){$stale|Remove-Item -Force}
$partNames=@("yuki-model-$Version.part01","yuki-model-$Version.part02")
$buffer=New-Object byte[] (8MB);$part=0
$hash=[Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA256)
$source=$null
try{
    $source=[IO.File]::OpenRead($modelSource)
    while($source.Position -lt $source.Length){
        $part++;if($part -gt 2){throw 'The local model exceeds the two-part release plan.'}
        $target=Join-Path $output $partNames[$part-1];$dest=[IO.File]::Create($target);$left=$chunkSize
        try{
            while($left -gt 0 -and ($read=$source.Read($buffer,0,[int][Math]::Min($buffer.Length,$left))) -gt 0){
                $dest.Write($buffer,0,$read)
                $hash.AppendData($buffer,0,$read)
                $left-=$read
            }
        }finally{$dest.Dispose()}
    }
    $modelHash=[BitConverter]::ToString($hash.GetHashAndReset()).Replace('-','').ToLowerInvariant()
}finally{if($source){$source.Dispose()};$hash.Dispose()}
if($part -ne 2){throw "Expected two model parts, got $part."}
$manifest=[ordered]@{version=$Version;modelFile=$modelName;modelSha256=$modelHash}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Candidate 'release-manifest.json') -Encoding ascii
if(Test-Path $archive){Remove-Item -LiteralPath $archive -Force}
Compress-Archive -Path $Candidate -DestinationPath $archive -CompressionLevel Optimal -Force
$releaseFiles=@($archive)
foreach($name in $partNames){$releaseFiles+=Join-Path $output $name}
foreach($path in $releaseFiles){
    if((Get-Item -LiteralPath $path).Length -ge 2147483648L){throw "Release file exceeds GitHub's per-file limit: $path"}
}
Write-Output "Three release files ready: $output"
