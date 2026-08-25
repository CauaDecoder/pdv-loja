param([Parameter(Mandatory=$true)][string]$Destination, [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."))
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Destination)) { throw "Destino de backup não existe: $Destination" }
$python = (Get-Command python).Source
$action = New-ScheduledTaskAction -Execute $python -Argument "-m scripts.backup_central `"$Destination`"" -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At "22:00"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "CaixaBasilicaBackup" -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Write-Host "Backup diário agendado para 22:00."
