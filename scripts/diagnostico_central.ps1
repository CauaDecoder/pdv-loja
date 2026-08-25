param([string]$BackupDestination = "")

function Get-LocalIPv4Candidates {
    $interfaces = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()

    foreach ($networkInterface in $interfaces) {
        if ($networkInterface.OperationalStatus -ne [System.Net.NetworkInformation.OperationalStatus]::Up) { continue }
        if ($networkInterface.NetworkInterfaceType -eq [System.Net.NetworkInformation.NetworkInterfaceType]::Loopback) { continue }

        $properties = $networkInterface.GetIPProperties()
        $gateway = $properties.GatewayAddresses |
            Where-Object { $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
            Select-Object -First 1

        foreach ($unicast in $properties.UnicastAddresses) {
            if ($unicast.Address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { continue }

            $ip = $unicast.Address.ToString()
            if ($ip -like "127.*" -or $ip -like "169.254.*") { continue }

            [PSCustomObject]@{
                Interface = $networkInterface.Name
                IP = $ip
                Gateway = if ($gateway) { $gateway.Address.ToString() } else { "sem gateway" }
                HasGateway = [bool]$gateway
            }
        }
    }
}
$root = Resolve-Path "$PSScriptRoot\.."
$drive = (Get-Item $root).PSDrive.Name
$volume = Get-Volume -DriveLetter $drive
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$issues = @()
if (-not $admin) { $issues += "Execute PowerShell como Administrador." }
if ($volume.FileSystem -ne "NTFS") { $issues += "O disco do banco precisa ser NTFS." }
if ((Get-Service W32Time).Status -ne "Running") { $issues += "O serviço de horário do Windows não está ativo." }
if ($BackupDestination -and -not (Test-Path $BackupDestination)) { $issues += "Destino externo de backup não existe." }
Write-Host "Computador: $env:COMPUTERNAME"
Write-Host "Disco: $($volume.FileSystem), livre $([math]::Round($volume.SizeRemaining / 1GB, 1)) GB"
$networkCandidates = @(Get-LocalIPv4Candidates | Sort-Object HasGateway -Descending)
if ($networkCandidates.Count -eq 0) {
    $issues += "Nenhum IPv4 local ativo foi encontrado. Verifique cabo/Wi-Fi e execute novamente."
} else {
    $gatewayCandidates = @($networkCandidates | Where-Object HasGateway)
    $displayCandidates = if ($gatewayCandidates.Count -gt 0) { $gatewayCandidates } else { $networkCandidates }
    foreach ($candidate in $displayCandidates) {
        $label = if ($candidate.HasGateway) { "IP local sugerido" } else { "IP local alternativo" }
        Write-Host "$label`: $($candidate.IP) | Interface: $($candidate.Interface) | Gateway: $($candidate.Gateway)"
    }
}
if ($issues.Count) { $issues | ForEach-Object { Write-Error $_ }; exit 1 }
Write-Host "Diagnóstico aprovado. Reserve o IP local sugerido para este computador no roteador."
