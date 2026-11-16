$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$count = 0
$drives = @()
$battery = @{ available = $false }
$last = ''
while ($true) {
    # Drives and battery move slowly; the loop only re-queries every 12 seconds and only
    # writes a line when something actually changed, so an idle desktop costs the worker nothing.
    if ($count % 2 -eq 0) {
        try { $drives = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 2' | ForEach-Object { $_.DeviceID }) } catch {}
        try {
            $cell = Get-CimInstance Win32_Battery | Select-Object -First 1
            if ($cell) { $battery = @{ available = $true; percent = $cell.EstimatedChargeRemaining; status = $cell.BatteryStatus } }
        } catch {}
    }
    $json = @{battery = $battery; drives = @($drives)} | ConvertTo-Json -Compress -Depth 4
    if ($json -cne $last -or $count % 10 -eq 0) { $last = $json; $json }
    $count++
    Start-Sleep -Seconds 6
}
