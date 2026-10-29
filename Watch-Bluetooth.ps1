$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$framework = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
$metadata = Join-Path $env:WINDIR 'System32\WinMetadata'
$references = @(
    (Join-Path $metadata 'Windows.Devices.winmd'),
    (Join-Path $metadata 'Windows.Foundation.winmd'),
    (Join-Path $framework 'System.Runtime.dll'),
    (Join-Path $framework 'System.Runtime.InteropServices.WindowsRuntime.dll'),
    (Join-Path $framework 'System.Runtime.WindowsRuntime.dll'),
    'System.dll', 'System.Core.dll', 'System.Web.Extensions.dll'
)
$source = @"
using System;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.Web.Script.Serialization;
using Windows.Devices.Enumeration;
using Windows.Devices.Bluetooth;
public static class DivoomBluetoothEvents {
    static readonly object Gate = new object();
    static readonly BlockingCollection<string> Messages = new BlockingCollection<string>();
    static readonly Dictionary<string, Dictionary<string, object>> Devices = new Dictionary<string, Dictionary<string, object>>();
    static int completed;
    static void Publish() {
        if (completed < 2) return;
        var rows = new List<object>();
        foreach (var row in Devices.Values)
            if (row.ContainsKey("System.Devices.Aep.IsConnected") && Object.Equals(row["System.Devices.Aep.IsConnected"], true)
                && row.ContainsKey("System.Devices.Aep.DeviceAddress"))
                rows.Add(new { Name = row["Name"], Address = row["System.Devices.Aep.DeviceAddress"] });
        Messages.Add(new JavaScriptSerializer().Serialize(new { Devices = rows }));
    }
    public static void Start() {
        var selectors = new [] { BluetoothDevice.GetDeviceSelectorFromConnectionStatus(BluetoothConnectionStatus.Connected),
            BluetoothLEDevice.GetDeviceSelectorFromConnectionStatus(BluetoothConnectionStatus.Connected) };
        for (int i = 0; i < selectors.Length; i++) {
            string prefix = i.ToString() + "/";
            var watcher = DeviceInformation.CreateWatcher(selectors[i], new [] { "System.Devices.Aep.DeviceAddress", "System.Devices.Aep.IsConnected" });
            watcher.Added += (sender, item) => { lock (Gate) {
                var row = new Dictionary<string, object>(); row["Name"] = item.Name;
                foreach (var property in item.Properties) row[property.Key] = property.Value;
                Devices[prefix + item.Id] = row; Publish();
            }};
            watcher.Updated += (sender, item) => { lock (Gate) {
                Dictionary<string, object> row;
                if (Devices.TryGetValue(prefix + item.Id, out row)) {
                    foreach (var property in item.Properties) row[property.Key] = property.Value;
                    Publish();
                }
            }};
            watcher.Removed += (sender, item) => { lock (Gate) { Devices.Remove(prefix + item.Id); Publish(); }};
            watcher.EnumerationCompleted += (sender, item) => { lock (Gate) { completed++; Publish(); }};
            watcher.Stopped += (sender, item) => Messages.CompleteAdding();
            Watchers.Add(watcher); watcher.Start();
        }
    }
    static readonly List<DeviceWatcher> Watchers = new List<DeviceWatcher>();
    public static string Next() { return Messages.Take(); }
}
"@
$parameters = New-Object System.CodeDom.Compiler.CompilerParameters
$parameters.GenerateInMemory = $true
$parameters.ReferencedAssemblies.AddRange([string[]]$references)
$provider = New-Object Microsoft.CSharp.CSharpCodeProvider
$result = $provider.CompileAssemblyFromSource($parameters, $source)
if ($result.Errors.HasErrors) { throw ($result.Errors | Out-String) }
[DivoomBluetoothEvents]::Start()
while ($true) { [Console]::WriteLine([DivoomBluetoothEvents]::Next()) }



