param([Parameter(Mandatory = $true)][string]$Plan)

$ErrorActionPreference = 'Stop'
$comparison = [StringComparison]::OrdinalIgnoreCase
$modelFile = 'Qwen3.8-4B-Q4_K_M.gguf'
$modelRelativePath = "resources\local-model\qwen\$modelFile"
$utf8 = [Text.UTF8Encoding]::new($false)

function Test-ReparsePoint([string]$Path) {
    return ([IO.File]::GetAttributes($Path) -band [IO.FileAttributes]::ReparsePoint) -ne 0
}

function Read-Json([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Write-UpdateLog([string]$Message) {
    [IO.File]::AppendAllText($logPath, "$(Get-Date -Format o) $Message" + [Environment]::NewLine, $utf8)
}

function Write-Result([string]$Status, [string]$Message) {
    $result = @{ status = $Status; version = $targetVersion; message = $Message } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText("$resultPath.tmp", $result, $utf8)
    [IO.File]::Move("$resultPath.tmp", $resultPath)
}

function Wait-ForExit([Diagnostics.Process]$Process, [int]$TimeoutMs) {
    return $null -eq $Process -or $Process.WaitForExit($TimeoutMs)
}

function Move-AppDirectory([string]$From, [string]$To) {
    # A scanner may briefly retain a handle after all Yuki processes have exited.
    for ($attempt = 1; $attempt -le 15; $attempt++) {
        try {
            [IO.Directory]::Move($From, $To)
            return
        } catch [IO.IOException] {
            if ($attempt -eq 15) { throw }
            Start-Sleep -Milliseconds 400
        }
    }
}

function Read-AppPackage([string]$Directory) {
    $exe = Join-Path $Directory 'yuki.exe'
    if (-not [IO.File]::Exists($exe) -or (Test-ReparsePoint $exe)) {
        throw 'Missing or invalid yuki.exe.'
    }
    $package = Read-Json (Join-Path $Directory 'resources\app\package.json')
    if ($package.name -cne 'yuki' -or $package.version -notmatch '^\d+\.\d+\.\d+$') {
        throw 'Invalid Yuki package identity.'
    }
    return $package
}

function Read-ReleaseManifest([string]$Directory, [string]$Version) {
    $manifest = Read-Json (Join-Path $Directory 'release-manifest.json')
    if ($manifest.version -cne "v$Version" -or $manifest.modelFile -cne $modelFile -or
        $manifest.modelSha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw 'The release manifest does not match the package.'
    }
    return $manifest
}

function Expand-AppArchive([string]$ArchivePath, [string]$ExpectedHash, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $file = [IO.File]::Open($ArchivePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ((Get-FileHash -InputStream $file -Algorithm SHA256).Hash -ne $ExpectedHash) {
            throw 'The downloaded ZIP failed its SHA-256 check.'
        }
        $file.Position = 0
        $zip = [IO.Compression.ZipArchive]::new($file, [IO.Compression.ZipArchiveMode]::Read, $true)
        try {
            $paths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            foreach ($entry in $zip.Entries) {
                $name = $entry.FullName.Replace('\', '/')
                $parts = $name.TrimEnd('/').Split('/')
                if ($parts[0] -cne 'yuki-win32-x64' -or ($parts.Length -eq 1 -and -not $name.EndsWith('/'))) {
                    throw "Entry outside Yuki's package directory: $name"
                }
                foreach ($part in $parts) {
                    if ($part -eq '' -or $part -match '[<>:"|?*\x00-\x1F]|[. ]$|^(CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])(\.|$)') {
                        throw "Invalid Windows path in the ZIP: $name"
                    }
                }
                $attributes = $entry.ExternalAttributes
                if (($attributes -band 0x400) -or (($attributes -shr 16) -band 0xF000) -eq 0xA000) {
                    throw "Link in the ZIP: $name"
                }
                if (-not $paths.Add($name.TrimEnd('/'))) {
                    throw "Duplicate path in the ZIP: $name"
                }
            }
            [IO.Compression.ZipFileExtensions]::ExtractToDirectory($zip, $Destination)
        } finally { $zip.Dispose() }
    } finally { $file.Dispose() }
}

function Preserve-Model([string]$OldApp, [string]$NewApp, [string]$ModelHash) {
    $oldModel = Join-Path $OldApp $modelRelativePath
    if (-not [IO.File]::Exists($oldModel)) { return }
    if ((Get-FileHash -LiteralPath $oldModel -Algorithm SHA256).Hash -ne $ModelHash) {
        throw 'The installed model is incompatible with the new release.'
    }
    $newModel = Join-Path $NewApp $modelRelativePath
    [IO.Directory]::CreateDirectory((Split-Path -Parent $newModel)) | Out-Null
    try {
        if (Test-ReparsePoint $oldModel) { throw 'The installed model is a link.' }
        New-Item -ItemType HardLink -Path $newModel -Target $oldModel | Out-Null
    } catch {
        [IO.File]::Copy($oldModel, $newModel)
        if ((Get-FileHash -LiteralPath $newModel -Algorithm SHA256).Hash -ne $ModelHash) {
            throw 'The copied model failed its SHA-256 check.'
        }
    }
}

function Start-Yuki([string]$Directory, [string]$ReadyFile = '') {
    $previousReadyFile = $env:YUKI_UPDATE_READY_FILE
    try {
        $env:YUKI_UPDATE_READY_FILE = $ReadyFile
        return Start-Process -FilePath (Join-Path $Directory 'yuki.exe') -WorkingDirectory $Directory -WindowStyle Hidden -PassThru
    } finally { $env:YUKI_UPDATE_READY_FILE = $previousReadyFile }
}

function Wait-ForStartup([Diagnostics.Process]$Process, [string]$ReadyFile) {
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($deadline.Elapsed.TotalSeconds -lt 60) {
        if ($Process.HasExited) { throw "The new Yuki exited with code $($Process.ExitCode)." }
        if ([IO.File]::Exists($ReadyFile) -and [IO.File]::ReadAllText($ReadyFile).Trim() -eq [string]$Process.Id) { return }
        Start-Sleep -Milliseconds 250
    }
    throw 'The new Yuki did not finish startup.'
}

$planPath = [IO.Path]::GetFullPath($Plan)
$stage = Split-Path -Parent $planPath
$stageParent = Split-Path -Parent $stage
$tempRoots = @($env:TEMP, $env:TMP, [IO.Path]::GetTempPath()) | Where-Object { $_ }
$validStage = $false
foreach ($tempRoot in $tempRoots) {
    if ([IO.Path]::GetFullPath($tempRoot).TrimEnd('\').Equals($stageParent, $comparison)) {
        $validStage = $true
        break
    }
}
if (-not $validStage -or (Split-Path -Leaf $stage) -notmatch '^yuki-update-[a-zA-Z0-9-]+$' -or
    (Test-ReparsePoint $stage) -or (Test-ReparsePoint $planPath)) {
    throw 'Invalid update staging directory.'
}
Set-Location -LiteralPath $stage
$resultPath = Join-Path $stage 'result.json'
$logPath = Join-Path $stage 'update.log'
$readyPath = Join-Path $stage 'startup-ready'
$targetVersion = $null
$oldProcess = $null
$newProcess = $null
$restartOld = $false
$originalMoved = $false
$replacementMoved = $false
$archiveValidated = $false
$workDirectory = $null
$failureMessage = '更新准备失败，文件已保留。'

try {
    $request = Read-Json $planPath
    $targetVersion = [string]$request.version
    $oldProcessId = [int]$request.pid
    $sha256 = [string]$request.sha256
    if ($targetVersion -notmatch '^\d+\.\d+\.\d+$' -or $oldProcessId -le 0 -or $oldProcessId -eq $PID -or $sha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw 'Invalid update plan.'
    }
    $archive = [IO.Path]::GetFullPath([string]$request.archive)
    if (-not (Split-Path -Parent $archive).Equals($stage, $comparison) -or
        [IO.Path]::GetExtension($archive) -ne '.zip' -or (Test-ReparsePoint $archive)) {
        throw 'Invalid update archive path.'
    }
    $archiveValidated = $true
    $installDir = [IO.Path]::GetFullPath([string]$request.installDir).TrimEnd('\')
    if ($installDir -notmatch '^[A-Za-z]:\\.+$' -or (Test-ReparsePoint $installDir) -or
        $stage.StartsWith($installDir + '\', $comparison)) {
        throw 'Invalid Yuki installation directory.'
    }
    $currentApp = Read-AppPackage $installDir
    $null = Read-ReleaseManifest $installDir $currentApp.version
    if ([version]$currentApp.version -ge [version]$targetVersion) { throw 'The version in the plan is not newer.' }
    $oldProcess = Get-Process -Id $oldProcessId -ErrorAction SilentlyContinue
    if ($oldProcess -and -not $oldProcess.HasExited) {
        try {
            if (-not (Join-Path $installDir 'yuki.exe').Equals($oldProcess.MainModule.FileName, $comparison)) {
                throw 'The running process does not match this installation.'
            }
        } catch {
            if (-not $oldProcess.HasExited) { throw }
        }
    }
    $restartOld = $true

    $parent = Split-Path -Parent $installDir
    $suffix = [Guid]::NewGuid().ToString('N').Substring(0, 12)
    $workDirectory = Join-Path $parent ".yuki-stage-$suffix"
    $oldDirectory = Join-Path $parent ".yuki-previous-$suffix"
    $candidate = Join-Path $workDirectory 'yuki-win32-x64'
    if ((Test-Path -LiteralPath $workDirectory) -or (Test-Path -LiteralPath $oldDirectory)) {
        $workDirectory = $null
        throw 'Update work directory is occupied.'
    }
    [IO.Directory]::CreateDirectory($workDirectory) | Out-Null
    Write-UpdateLog "Preparing Yuki $targetVersion in $workDirectory"
    $failureMessage = '更新包校验或解压失败。请检查磁盘空间后重试。'
    Expand-AppArchive $archive $sha256 $workDirectory
    $newApp = Read-AppPackage $candidate
    if ($newApp.version -cne $targetVersion) { throw 'Version in the archive does not match the update plan.' }
    $newManifest = Read-ReleaseManifest $candidate $targetVersion
    if (Test-Path -LiteralPath (Join-Path $candidate $modelRelativePath)) {
        throw 'The update ZIP unexpectedly includes model weights.'
    }
    $failureMessage = '无法沿用已安装的本地模型。请按新版发布说明手动升级。'
    Preserve-Model $installDir $candidate $newManifest.modelSha256

    $failureMessage = '无法写入 Yuki 的安装目录。请检查目录权限后重试。'
    $icacls = Join-Path $env:SystemRoot 'System32\icacls.exe'
    & $icacls $candidate /grant '*S-1-15-2-1:(OI)(CI)(RX)' /T /Q | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unable to grant Electron sandbox read access (icacls $LASTEXITCODE)." }

    $failureMessage = 'Yuki 未完全退出。请关闭 Yuki 后重试。'
    if (-not (Wait-ForExit $oldProcess 60000)) { throw 'The running Yuki did not exit.' }
    $failureMessage = '无法替换程序文件。请关闭占用程序目录的窗口后重试。'
    Write-UpdateLog 'Switching app directories.'
    Move-AppDirectory $installDir $oldDirectory
    $originalMoved = $true
    Move-AppDirectory $candidate $installDir
    $replacementMoved = $true
    $failureMessage = '新版未能启动，已恢复旧版。'
    $newProcess = Start-Yuki $installDir $readyPath
    Wait-ForStartup $newProcess $readyPath
    # Startup is the commit point. Reporting or cleanup failures cannot undo it.
    try { Write-UpdateLog "Updated to $targetVersion. Previous files: $oldDirectory" } catch {}
    try { Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue } catch {}
    try { Write-Result 'success' '' } catch { try { Write-UpdateLog $_.ToString() } catch {} }
} catch {
    $details = $_.ToString()
    try { Write-UpdateLog $details } catch {}
    if ($originalMoved) {
        try {
            if ($newProcess -and -not $newProcess.HasExited) {
                $taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
                & $taskkill /PID $newProcess.Id /T /F 2>&1 | Out-Null
                if (-not (Wait-ForExit $newProcess 10000)) { throw 'The failed Yuki could not be stopped.' }
            }
            if ($replacementMoved) { Move-AppDirectory $installDir $candidate }
            Move-AppDirectory $oldDirectory $installDir
        } catch {
            $failureMessage = "自动恢复失败。旧版程序保存在 $oldDirectory"
            $restartOld = $false
            try { Write-UpdateLog $_.ToString() } catch {}
        }
    }
    if ($archiveValidated) {
        try { Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue } catch {}
    }
    try { Write-Result 'error' $failureMessage } catch {}
    if ($restartOld -and (Wait-ForExit $oldProcess 30000)) {
        try { Start-Yuki $installDir | Out-Null } catch { try { Write-UpdateLog $_.ToString() } catch {} }
    }
    exit 1
} finally {
    if ($workDirectory -and (Test-Path -LiteralPath $workDirectory) -and
        (Split-Path -Parent ([IO.Path]::GetFullPath($workDirectory))).Equals($parent, $comparison) -and
        (Split-Path -Leaf $workDirectory) -match '^\.yuki-stage-[a-f0-9]{12}$' -and
        -not (Test-ReparsePoint $workDirectory)) {
        Remove-Item -LiteralPath $workDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}
