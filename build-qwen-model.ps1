$ErrorActionPreference='Stop'
$modelRoot=Join-Path $PSScriptRoot 'local-model/qwen'
$model=Join-Path $modelRoot 'Qwen3.8-4B-Q4_K_M.gguf'
$expected='DEC96E8CF2E11B613BB46513DEC485377F9CA5A351E71712EE0E244F287C6790'
New-Item -ItemType Directory -Path $modelRoot -Force | Out-Null
if(-not(Test-Path $model)){
    Invoke-WebRequest -Uri 'https://huggingface.co/empero-ai/Qwen3.8-4B-Distill-GGUF/resolve/391fc7d/Qwen3.8-4B-Q4_K_M.gguf' -OutFile $model
}
$actual=(Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash
if($actual -ne $expected){throw 'Qwen model checksum mismatch; remove the damaged local file and rebuild.'}
Write-Output "Qwen model ready: $model"
