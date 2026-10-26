param(
    [ValidateSet('play','pause','previous','next','seek')][string]$Command,
    [string]$ExpectedApp,
    [double]$Position = 0,
    [string]$ExpectedTitle,
    [string]$ExpectedArtist
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
    function Await-WinRT($Operation, $ResultType) {
        $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        if (-not $task.Wait(2000)) { throw '播放器响应超时' }
        $task.Result
    }
    function Get-MediaPosition($Timeline, $Info) {
        $value = $Timeline.Position.TotalSeconds
        if ($Info.PlaybackStatus.ToString() -eq 'Playing') {
            $elapsed = ([DateTimeOffset]::UtcNow - $Timeline.LastUpdatedTime).TotalSeconds
            $rate = if ($null -eq $Info.PlaybackRate) { 1 } else { $Info.PlaybackRate }
            $value += [math]::Max(0, $elapsed) * $rate
        }
        [math]::Max($Timeline.StartTime.TotalSeconds, [math]::Min($Timeline.EndTime.TotalSeconds, $value))
    }
    $manager = Await-WinRT ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
    $session = $manager.GetCurrentSession()
    if (-not $session) { throw '未检测到播放会话，请先在播放器中打开音乐' }
    if ($session.SourceAppUserModelId -cne $ExpectedApp) { throw '当前播放器已切换，请刷新后重试' }
    $controls = $session.GetPlaybackInfo().Controls
    $operation = switch ($Command) {
        'seek' {
            $expectedProps = Await-WinRT ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
            if ($expectedProps.Title -cne $ExpectedTitle -or $expectedProps.Artist -cne $ExpectedArtist) { throw '曲目已切换，请重新调整进度' }
            $timeline = $session.GetTimelineProperties()
            if (-not $controls.IsPlaybackPositionEnabled) { throw '当前播放器不支持调整进度' }
            if ([double]::IsNaN($Position) -or [double]::IsInfinity($Position) -or $Position -lt $timeline.StartTime.TotalSeconds -or $Position -gt $timeline.EndTime.TotalSeconds) { throw '播放进度超出曲目范围' }
            $session.TryChangePlaybackPositionAsync([long]([math]::Round($Position * 10000000)))
        }
        'play' { if (-not $controls.IsPlayEnabled) { throw '当前播放器不支持播放' }; $session.TryPlayAsync() }
        'pause' { if (-not $controls.IsPauseEnabled) { throw '当前播放器不支持暂停' }; $session.TryPauseAsync() }
        'previous' { if (-not $controls.IsPreviousEnabled) { throw '当前播放器不支持上一首' }; $session.TrySkipPreviousAsync() }
        'next' { if (-not $controls.IsNextEnabled) { throw '当前播放器不支持下一首' }; $session.TrySkipNextAsync() }
    }
    if (-not (Await-WinRT $operation ([bool]))) { throw '播放器未接受操作，请在系统播放器中检查' }
    $props = Await-WinRT ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
    $timeline = $session.GetTimelineProperties()
    $info = $session.GetPlaybackInfo()
    @{ ok = $true; media = @{ available = $true; title = $props.Title; artist = $props.Artist; app = $session.SourceAppUserModelId; status = $info.PlaybackStatus.ToString(); observedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds(); rate = $info.PlaybackRate; start = $timeline.StartTime.TotalSeconds; position = (Get-MediaPosition $timeline $info); duration = $timeline.EndTime.TotalSeconds; controls = @{ seek = $info.Controls.IsPlaybackPositionEnabled; play = $info.Controls.IsPlayEnabled; pause = $info.Controls.IsPauseEnabled; previous = $info.Controls.IsPreviousEnabled; next = $info.Controls.IsNextEnabled } } } | ConvertTo-Json -Compress -Depth 5
} catch {
    @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
}
