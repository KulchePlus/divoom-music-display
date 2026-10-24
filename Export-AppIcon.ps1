param([string]$Executable, [string]$OutputPath, [string]$AppId)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class AppIconExport {
    [StructLayout(LayoutKind.Sequential)]
    public struct Size { public int Width; public int Height; }
    [ComImport, Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IImageFactory {
        [PreserveSig] int GetImage(Size size, uint flags, out IntPtr bitmap);
    }
    [DllImport("shell32.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
    public static extern void SHCreateItemFromParsingName(string name, IntPtr context, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out IImageFactory factory);
    [DllImport("gdi32.dll")]
    public static extern bool DeleteObject(IntPtr bitmap);
    public static void SaveApp(string appId, string output) {
        IImageFactory factory = null;
        IntPtr bitmap = IntPtr.Zero;
        try {
            Guid iid = typeof(IImageFactory).GUID;
            SHCreateItemFromParsingName("shell:AppsFolder\\" + appId, IntPtr.Zero, ref iid, out factory);
            int result = factory.GetImage(new Size { Width=128, Height=128 }, 5, out bitmap);
            Marshal.ThrowExceptionForHR(result);
            using (var image = System.Drawing.Image.FromHbitmap(bitmap)) {
                image.Save(output, System.Drawing.Imaging.ImageFormat.Png);
            }
        } finally {
            if (bitmap != IntPtr.Zero) DeleteObject(bitmap);
            if (factory != null) Marshal.ReleaseComObject(factory);
        }
    }
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern uint PrivateExtractIcons(string file, int index, int width, int height, IntPtr[] icons, uint[] ids, uint count, uint flags);
    [DllImport("user32.dll")]
    public static extern bool DestroyIcon(IntPtr icon);
}
'@ -ReferencedAssemblies System.Drawing
if ($AppId) {
    try { [AppIconExport]::SaveApp($AppId, $OutputPath); exit 0 } catch { }
    $stem = [IO.Path]::GetFileNameWithoutExtension($AppId)
    $candidate = Get-StartApps | Where-Object { $_.AppID -eq $AppId -or $_.Name -eq $stem -or $_.Name -like "$stem *" } | Select-Object -First 1
    if ($candidate) {
        try { [AppIconExport]::SaveApp($candidate.AppID, $OutputPath); exit 0 } catch { }
    }
    if (Test-Path -LiteralPath $AppId -PathType Leaf) { $Executable = $AppId }
    if (-not $Executable) {
        $Executable = Get-Process -Name $stem -ErrorAction SilentlyContinue | Where-Object { $_.Path } | Select-Object -First 1 -ExpandProperty Path
    }
    if (-not $Executable) { throw "Application icon not found: $AppId" }
}
$handles = New-Object IntPtr[] 1
$ids = New-Object uint32[] 1
$count = [AppIconExport]::PrivateExtractIcons($Executable, 0, 128, 128, $handles, $ids, 1, 0)
if ($count -ne 1 -or $handles[0] -eq [IntPtr]::Zero) { throw 'Could not extract application icon.' }
try {
    $icon = [System.Drawing.Icon]::FromHandle($handles[0])
    $bitmap = $icon.ToBitmap()
    try { $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png) }
    finally { $bitmap.Dispose(); $icon.Dispose() }
} finally { [void][AppIconExport]::DestroyIcon($handles[0]) }
