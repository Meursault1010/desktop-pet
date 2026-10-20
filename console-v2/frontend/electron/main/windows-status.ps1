$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$manager = $null
$mediaError = '未检测到播放会话'
try {
    $null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
    function Await-WinRT($Operation, $ResultType) {
        $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        if (-not $task.Wait(2000)) { throw '媒体读取超时' }
        $task.Result
    }
    $manager = Await-WinRT ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
} catch { $mediaError = '当前系统不支持媒体会话读取' }
$count = 0
$drives = @()
$battery = @{ available = $false }
while ($true) {
    $media = @{ available = $false; status = $mediaError }
    try {
        if ($manager) {
            $session = $manager.GetCurrentSession()
            if ($session) {
                $props = Await-WinRT ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
                $timeline = $session.GetTimelineProperties()
                $media = @{ available = $true; title = $props.Title; artist = $props.Artist; app = $session.SourceAppUserModelId; status = $session.GetPlaybackInfo().PlaybackStatus.ToString(); position = $timeline.Position.TotalSeconds; duration = $timeline.EndTime.TotalSeconds }
            }
        }
    } catch { $media = @{ available = $false; status = '播放器暂不可读取' } }
    if ($count % 4 -eq 0) {
        try { $drives = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 2' | ForEach-Object { $_.DeviceID }) } catch {}
        try {
            $cell = Get-CimInstance Win32_Battery | Select-Object -First 1
            if ($cell) { $battery = @{ available = $true; percent = $cell.EstimatedChargeRemaining; status = $cell.BatteryStatus } }
        } catch {}
    }
    @{media = $media; battery = $battery; drives = @($drives)} | ConvertTo-Json -Compress -Depth 4
    $count++
    Start-Sleep -Seconds 3
}
