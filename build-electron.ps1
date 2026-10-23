param([string]$Python = 'python', [switch]$SkipInstall)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'build-selection.ps1')
& (Join-Path $PSScriptRoot 'build-ocr.ps1') -SkipInstall:$SkipInstall
if($LASTEXITCODE){throw 'Offline OCR build failed'}
$petRoot=Join-Path $PSScriptRoot 'console-v2'
$buildRoot=Join-Path $PSScriptRoot '.electron-build'
$buildPython=Join-Path $buildRoot 'venv\Scripts\python.exe'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
if(-not(Test-Path -LiteralPath $buildPython)){
    & $Python -m venv (Join-Path $buildRoot 'venv')
    if($LASTEXITCODE){throw 'Unable to create isolated build environment'}
}
if(-not $SkipInstall){
    & $buildPython -m pip install 'PySide6==6.10.2' 'pyinstaller==6.19.0' 'PyAudioWPatch==0.2.12.8' 'opencv-python-headless==4.11.0.86'
    if($LASTEXITCODE){throw 'Build dependency installation failed'}
}
Push-Location $petRoot
$savedBuildPath=$env:Path
try {
    # Unrelated native toolchains (e.g. Poppler) can provide incompatible ICU
    # DLLs earlier on PATH. Freeze against Windows' ICU used by Qt at runtime.
    $env:Path=(Split-Path $buildPython)+';'+$env:SystemRoot+'\System32;'+$env:SystemRoot
    & $buildPython -m PyInstaller --noconfirm --clean --onedir --console --name yuki-backend `
        --distpath (Join-Path $buildRoot 'python-dist') --workpath (Join-Path $buildRoot 'python-work') `
        --specpath $buildRoot --add-data ((Join-Path $petRoot 'assets') + ';assets') `
        --add-binary ((Join-Path $env:SystemRoot 'System32\icuuc.dll') + ';.') 'pet_backend.py'
    if($LASTEXITCODE){throw 'Python backend build failed'}
    # Python may ship an older VC runtime than Qt. The bootloader loads the
    # root copy first, so use Qt's backward-compatible runtime consistently.
    $qtPackage=Join-Path $buildRoot 'venv\Lib\site-packages\PySide6'
    $frozenInternal=Join-Path $buildRoot 'python-dist\yuki-backend\_internal'
    foreach($dll in @('VCRUNTIME140.dll','VCRUNTIME140_1.dll')){
        Copy-Item -LiteralPath (Join-Path $qtPackage $dll) -Destination (Join-Path $frozenInternal $dll) -Force
    }
} finally {$env:Path=$savedBuildPath;Pop-Location}
Push-Location (Join-Path $petRoot 'frontend')
try {
    if(-not $SkipInstall){& npm.cmd ci --no-audit --no-fund;if($LASTEXITCODE){throw 'npm ci failed'}}
    & node 'node_modules/electron/install.js'
    if($LASTEXITCODE){throw 'Electron runtime installation failed'}
    & npm.cmd run build
    if($LASTEXITCODE){throw 'Frontend build failed'}
    & node 'electron/scripts/package.cjs'
    if($LASTEXITCODE){throw 'Electron package failed'}
} finally {Pop-Location}
