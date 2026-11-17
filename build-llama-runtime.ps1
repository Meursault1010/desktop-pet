$ErrorActionPreference='Stop'
$buildRoot=Join-Path $PSScriptRoot '.electron-build'
$runtime=Join-Path $buildRoot 'llama-runtime-b12464'
$archive=Join-Path $buildRoot 'llama-b12464-bin-win-vulkan-x64.zip'
$expected='839455639ced0f6ad50e971d37c89050e0e8b952c12e1c62a78823940fb93073'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
if(-not(Test-Path (Join-Path $runtime 'llama-server.exe'))){
    if(-not(Test-Path $archive)){
        Invoke-WebRequest -Uri 'https://github.com/ggml-org/llama.cpp/releases/download/b12464/llama-b12464-bin-win-vulkan-x64.zip' -OutFile $archive
    }
    $actual=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual -ne $expected){throw 'llama.cpp runtime checksum mismatch'}
    $temporary=Join-Path $buildRoot 'llama-runtime-extract'
    if(Test-Path $temporary){Remove-Item -LiteralPath $temporary -Recurse -Force}
    Expand-Archive -LiteralPath $archive -DestinationPath $temporary -Force
    if(-not(Test-Path (Join-Path $temporary 'llama-server.exe'))){throw 'llama.cpp archive is missing llama-server.exe'}
    Move-Item -LiteralPath $temporary -Destination $runtime
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ggml-org/llama.cpp/b12464/LICENSE' -OutFile (Join-Path $runtime 'LICENSE')
}
Write-Output "llama.cpp runtime ready: $runtime"
