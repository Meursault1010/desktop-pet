param([string]$Python = 'python', [switch]$SkipInstall)
$ErrorActionPreference='Stop'
$buildRoot=Join-Path $PSScriptRoot '.electron-build'
$ocrPython=Join-Path $buildRoot 'ocr-venv/Scripts/python.exe'
if(-not(Test-Path -LiteralPath $ocrPython)){
    & $Python -m venv (Join-Path $buildRoot 'ocr-venv')
    if($LASTEXITCODE){throw 'OCR environment creation failed'}
}
if(-not $SkipInstall){
    & $ocrPython -m pip install -r (Join-Path $PSScriptRoot 'tools/ocr/requirements-lock.txt')
    if($LASTEXITCODE){throw 'OCR dependency installation failed'}
}
& $ocrPython -m PyInstaller --noconfirm --clean --onedir --console --name yuki-ocr --collect-all rapidocr_onnxruntime --collect-all pyclipper --distpath (Join-Path $buildRoot 'ocr-dist') --workpath (Join-Path $buildRoot 'ocr-work') --specpath $buildRoot (Join-Path $PSScriptRoot 'tools/ocr/worker.py')
if($LASTEXITCODE){throw 'OCR build failed'}
