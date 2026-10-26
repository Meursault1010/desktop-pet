$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$count = 0
$drives = @()
$battery = @{ available = $false }
while ($true) {
    if ($count % 4 -eq 0) {
        try { $drives = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 2' | ForEach-Object { $_.DeviceID }) } catch {}
        try {
            $cell = Get-CimInstance Win32_Battery | Select-Object -First 1
            if ($cell) { $battery = @{ available = $true; percent = $cell.EstimatedChargeRemaining; status = $cell.BatteryStatus } }
        } catch {}
    }
    @{battery = $battery; drives = @($drives)} | ConvertTo-Json -Compress -Depth 4
    $count++
    Start-Sleep -Seconds 3
}
