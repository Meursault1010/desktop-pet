$ErrorActionPreference = 'Stop'
$petStage = $PSScriptRoot
$petTarget = 'C:\Users\meursault\Desktop\desktop-pet'
$petResolved = (Resolve-Path -LiteralPath $petTarget).Path
if ($petResolved -ne $petTarget -or -not (Test-Path -LiteralPath (Join-Path $petTarget 'pet_backend.py'))) {
    throw '目标目录不符合预期，已停止。'
}
if (Get-Process -Name 'xiaoju-console' -ErrorAction SilentlyContinue) {
    throw '请先通过托盘菜单完全退出小橘，再运行此脚本。'
}
$petPython = Join-Path $petTarget '.venv\Scripts\python.exe'
Push-Location $petStage
try {
    & $petPython -m unittest test_action_player test_idle_animation test_idle_window test_console test_ipc
    if ($LASTEXITCODE) { throw '回归测试失败，未修改桌面项目。' }
    Push-Location (Join-Path $petStage 'frontend')
    try {
        $env:CARGO_HOME = Join-Path $petStage '.toolchain\cargo'
        $env:RUSTUP_HOME = Join-Path $petStage '.toolchain\rustup'
        $env:PATH = "$env:CARGO_HOME\bin;$env:PATH"
        & node --experimental-strip-types --test tests/commandQueue.test.mjs
        if ($LASTEXITCODE) { throw '前端测试失败，未修改桌面项目。' }
        & npm.cmd run tauri -- build --no-bundle
        if ($LASTEXITCODE) { throw '控制台编译失败，未修改桌面项目。' }
    } finally { Pop-Location }
    $petBackup = Join-Path $petStage ('backup-actions-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $petBackup | Out-Null
    $petFiles = @('pet.py','pet_backend.py','action_player.py','test_action_player.py','test_ipc.py','build_action_library.py','repack_actions.py','finalize_actions.py','ACTION_LIBRARY.md','frontend\src\App.tsx','frontend\src\components\ActionLibrary.tsx','frontend\src\components\ActionLibrary.css','frontend\src-tauri\src\main.rs')
    $petFolders = @('assets\actions','frontend\public\actions','action-work','qa\actions')
    foreach ($petRelative in ($petFiles + $petFolders + @('app\xiaoju-console.exe'))) {
        $petExisting = Join-Path $petTarget $petRelative
        if (Test-Path -LiteralPath $petExisting) {
            $petBackupItem = Join-Path $petBackup $petRelative
            New-Item -ItemType Directory -Path (Split-Path -Parent $petBackupItem) -Force | Out-Null
            Copy-Item -LiteralPath $petExisting -Destination $petBackupItem -Recurse
        }
    }
    foreach ($petRelative in ($petFiles + $petFolders)) {
        $petDestination = Join-Path $petTarget $petRelative
        New-Item -ItemType Directory -Path (Split-Path -Parent $petDestination) -Force | Out-Null
        if ($petFolders -contains $petRelative) {
            New-Item -ItemType Directory -Path $petDestination -Force | Out-Null
            Get-ChildItem -LiteralPath (Join-Path $petStage $petRelative) | Copy-Item -Destination $petDestination -Recurse -Force
        } else {
            Copy-Item -LiteralPath (Join-Path $petStage $petRelative) -Destination $petDestination -Force
        }
    }
    Copy-Item -LiteralPath (Join-Path $petStage 'frontend\src-tauri\target\release\xiaoju-console.exe') -Destination (Join-Path $petTarget 'app\xiaoju-console.exe') -Force
    Write-Host "动作库部署完成。备份：$petBackup"
    Write-Host '运行桌面项目的 start.bat，在左侧打开动作库。原始图片及个人设置没有修改。'
} finally { Pop-Location }
