param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
    [int]$Port = 8765,
    [string]$PythonPath = ""
)
$ErrorActionPreference = "Stop"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $admin) {
    throw "Abra o PowerShell como Administrador antes de instalar o servidor."
}

if (-not $PythonPath) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $PythonPath = (& $pythonCommand.Source -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
    }
}
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath.Trim())) {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $PythonPath = (& $pyCommand.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
    }
}

$python = $PythonPath.Trim()
if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    throw "Python real nao encontrado. Informe -PythonPath com o caminho retornado por: python -c `"import sys; print(sys.executable)`""
}

$existingTask = Get-ScheduledTask -TaskName "CaixaBasilicaCentral" -ErrorAction SilentlyContinue
if ($existingTask) {
    Stop-ScheduledTask -TaskName "CaixaBasilicaCentral" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}
$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $probe.Connect("127.0.0.1", $Port)
    throw "A porta $Port ja esta em uso. Encerre o servidor manual com Ctrl+C e execute novamente."
} catch [System.Net.Sockets.SocketException] {
    # Porta livre: instalacao pode continuar.
} finally {
    $probe.Dispose()
}

$action = New-ScheduledTaskAction -Execute $python -Argument "-m app.server" -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "CaixaBasilicaCentral" -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
if (-not (Get-NetFirewallRule -DisplayName "Caixa Basilica Central" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Caixa Basilica Central" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
}
Start-ScheduledTask -TaskName "CaixaBasilicaCentral"

$ready = $false
for ($attempt = 1; $attempt -le 15; $attempt++) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.Connect("127.0.0.1", $Port)
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    } finally {
        $client.Dispose()
    }
}

if (-not $ready) {
    $result = (Get-ScheduledTaskInfo -TaskName "CaixaBasilicaCentral").LastTaskResult
    throw "A tarefa foi criada, mas o servidor nao abriu a porta $Port. LastTaskResult: $result"
}

Write-Host "Servidor instalado e iniciado com $python na porta $Port."
