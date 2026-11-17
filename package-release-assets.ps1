param([string]$Version='v1.1.1',[string]$Candidate=(Join-Path $PSScriptRoot 'releases/electron/yuki-win32-x64-release-candidate-v2/yuki-win32-x64'))
$ErrorActionPreference='Stop'
$tag=$Version.TrimStart('v')
$parent=Split-Path -Parent $Candidate
$folder=Split-Path -Leaf $Candidate
$output=Join-Path $PSScriptRoot "releases/electron/release-assets-v$tag"
$archive=Join-Path $output "yuki-win32-x64-$Version.tar.gz"
$chunkSize=1800000000L
if(-not(Test-Path (Join-Path $Candidate 'yuki.exe'))){throw "Candidate not found: $Candidate"}
New-Item -ItemType Directory -Path $output -Force | Out-Null
Get-ChildItem -LiteralPath $output -Filter "yuki-win32-x64-$Version.tar.gz.part*" -File -ErrorAction SilentlyContinue | Remove-Item -Force
if(Test-Path $archive){Remove-Item -LiteralPath $archive -Force}
& tar.exe -czf $archive -C $parent $folder
if($LASTEXITCODE -ne 0){throw "Portable archive creation failed ($LASTEXITCODE)"}
$source=[IO.File]::OpenRead($archive)
$buffer=New-Object byte[] (8MB)
$part=0
$sums=[System.Collections.Generic.List[string]]::new()
try{
    while($source.Position -lt $source.Length){
        $part++
        $name="yuki-win32-x64-$Version.tar.gz.part{0:D2}" -f $part
        $target=Join-Path $output $name
        $dest=[IO.File]::Create($target)
        $left=$chunkSize
        try{
            while($left -gt 0 -and ($read=$source.Read($buffer,0,[int][Math]::Min($buffer.Length,$left))) -gt 0){$dest.Write($buffer,0,$read);$left-=$read}
        }finally{$dest.Dispose()}
        if((Get-Item -LiteralPath $target).Length -ge 2147483648L){throw "Release part exceeds GitHub's per-file limit: $name"}
        $hash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        $sums.Add("$hash *$name")
        Write-Output ("Part {0}: {1:N2} GB" -f $part,((Get-Item -LiteralPath $target).Length/1GB))
    }
}finally{$source.Dispose()}
$whole=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$sums.Add("$whole *$(Split-Path -Leaf $archive)")
Set-Content -LiteralPath (Join-Path $output 'sha256sums.txt') -Value $sums -Encoding ascii
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install-yuki.ps1') -Destination $output
Write-Output "Release assets ready: $output"
