$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,Windows.Media.Control,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStreamWithContentType,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IInputStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStreamReference,Windows.Storage.Streams,ContentType=WindowsRuntime]
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
public static class CoverReader {
    [DllImport("shcore.dll", EntryPoint="CreateStreamOverRandomAccessStream", PreserveSig=false)]
    static extern void SHCreateStreamOverRandomAccessStream([MarshalAs(UnmanagedType.IUnknown)] object stream, ref Guid iid, out IStream result);
    public static byte[] Read(object value) {
        IStream stream = null;
        try {
            Guid iid = typeof(IStream).GUID;
            SHCreateStreamOverRandomAccessStream(value, ref iid, out stream);
            System.Runtime.InteropServices.ComTypes.STATSTG stat;
            stream.Stat(out stat, 1);
            if (stat.cbSize <= 0 || stat.cbSize > 5242880) throw new IOException("Invalid cover size");
            byte[] bytes = new byte[(int)stat.cbSize];
            IntPtr count = Marshal.AllocHGlobal(4);
            try {
                stream.Seek(0, 0, IntPtr.Zero);
                stream.Read(bytes, bytes.Length, count);
                if (Marshal.ReadInt32(count) != bytes.Length) throw new IOException("Incomplete cover read");
            } finally { Marshal.FreeHGlobal(count); }
            return bytes;
        } finally {
            if (stream != null) Marshal.ReleaseComObject(stream);
        }
    }
}
'@
function Await-WinRT($Operation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    try {
        if (-not $task.Wait(10000)) { throw 'Windows media session request timed out.' }
    } catch { throw $task.Exception.GetBaseException() }
    $task.Result
}
$manager = Await-WinRT ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$currentSession = $manager.GetCurrentSession()
foreach ($session in $manager.GetSessions()) {
    $media = Await-WinRT ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
    $cover = $null
    $coverError = $null
    $coverSize = $null
    if ($media.Thumbnail) {
        $stream = $null
        $reader = $null
        try {
            $stream = Await-WinRT ($media.Thumbnail.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
            $bytes = [CoverReader]::Read($stream)
            $coverSize = $bytes.Length
            if ($coverSize -gt 0 -and $coverSize -le 5242880) {
                $cover = [Convert]::ToBase64String($bytes)
            }
            if (-not $cover) { $coverError = "Empty or inaccessible stream; Size=$coverSize; Type=$($stream.GetType().FullName)" }
        } catch { $coverError = $_.Exception.ToString() } finally {
            if ($reader) { try { $reader.Dispose() } catch { } }
            if ($stream) { try { ([System.IDisposable]$stream).Dispose() } catch { } }
        }
    }
    [PSCustomObject]@{ App = $session.SourceAppUserModelId; Title = $media.Title; Artist = $media.Artist; Status = [string]$session.GetPlaybackInfo().PlaybackStatus; Cover = $cover; HasThumbnail = ($null -ne $media.Thumbnail); CoverSize = $coverSize; CoverError = $coverError; Current = ($currentSession -and $currentSession.SourceAppUserModelId -eq $session.SourceAppUserModelId) } | ConvertTo-Json -Compress
}
