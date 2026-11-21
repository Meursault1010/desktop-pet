param(
  [Parameter(Mandatory=$true)][string]$TargetExe,
  [Parameter(Mandatory=$true)][string]$IconPath
)
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($TargetExe)
$shell = New-Object -ComObject WScript.Shell
$desktopPaths = @(
  [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory),
  [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonDesktopDirectory)
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class YukiShortcutRefresh { [DllImport("shell32.dll", CharSet=CharSet.Unicode)] public static extern void SHChangeNotify(int eventId, uint flags, string item1, IntPtr item2); }'
foreach ($desktop in $desktopPaths) {
  Get-ChildItem -LiteralPath $desktop -Filter '*.lnk' -File | ForEach-Object {
    $shortcut = $shell.CreateShortcut($_.FullName)
    if (-not $shortcut.TargetPath) { return }
    try { $linkTarget = [IO.Path]::GetFullPath($shortcut.TargetPath) } catch { return }
    if ([string]::Equals($linkTarget, $target, [StringComparison]::OrdinalIgnoreCase)) {
      $shortcut.IconLocation = "$IconPath,0"
      $shortcut.Save()
      [YukiShortcutRefresh]::SHChangeNotify(0x2000, 0x5, $_.FullName, [IntPtr]::Zero)
    }
  }
}
