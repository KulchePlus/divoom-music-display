$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Devices.Enumeration.DeviceInformation,Windows.Devices.Enumeration,ContentType=WindowsRuntime]
$null = [Windows.Devices.Enumeration.DeviceInformationCollection,Windows.Devices.Enumeration,ContentType=WindowsRuntime]
$null = [Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
$null = [Windows.Devices.Bluetooth.BluetoothLEDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
function Await-WinRT($Operation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    if (-not $task.Wait(15000)) { throw 'Bluetooth enumeration timed out.' }
    $task.GetAwaiter().GetResult()
}
# Query both Bluetooth transports; inspect actual connection state explicitly.
$selectors = @(
    [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromConnectionStatus(1),
    [Windows.Devices.Bluetooth.BluetoothLEDevice]::GetDeviceSelectorFromConnectionStatus(1)
)
$properties = [string[]]@('System.Devices.Aep.DeviceAddress', 'System.Devices.Aep.IsConnected')
foreach ($selector in $selectors) {
    $devices = Await-WinRT ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync(
        $selector, $properties
    )) ([Windows.Devices.Enumeration.DeviceInformationCollection])
    foreach ($device in $devices) {
        $address = ''; $connected = $false
        foreach ($property in $device.Properties) {
            if ($property.Key -eq 'System.Devices.Aep.DeviceAddress') { $address = [string]$property.Value }
            if ($property.Key -eq 'System.Devices.Aep.IsConnected') { $connected = $property.Value -eq $true }
        }
        if ($connected -and $address) {
            @{ Name = $device.Name; Address = $address } | ConvertTo-Json -Compress
        }
    }
}
