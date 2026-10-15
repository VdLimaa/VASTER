<#
.SYNOPSIS
  Sobe o Masterset BR em localhost no Windows: banco, ingestao e tela.

.DESCRIPTION
  Gemeo de scripts/subir.sh. Os mesmos passos, na mesma ordem. A espera pelo
  Postgres mora em `python -m ingest ping`, para nao existir um laco de
  retentativa em bash e outro aqui.

  Script que saiu de um .zip baixado vem marcado pelo Windows e nao roda
  direto. Chame assim, ou use scripts\subir.bat, que ja faz isso:

      powershell -ExecutionPolicy Bypass -File .\scripts\subir.ps1

  Sem acento de proposito: console do Windows em cp850 tropeca neles.

.PARAMETER Rapido
  So o catalogo ocidental (ingles e portugues), ~1 minuto, no lugar dos ~7 do
  catalogo inteiro. O japones entra depois, rodando `python -m ingest sets`,
  `cards`, `details` e `slots` sem --region.

.PARAMETER Dev
  Dois processos, com recarga instantanea: uvicorn numa janela nova, Vite
  nesta, e a tela em http://127.0.0.1:5173.

.PARAMETER SoTela
  Pula a ingestao, para quando o banco ja esta cheio.

.PARAMETER Porta
  Porta da API. Padrao 8000.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\subir.ps1 -Rapido
#>
param(
  [switch]$Rapido,
  [switch]$Dev,
  [switch]$SoTela,
  [int]$Porta = 8000
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

function Passo([string]$texto) { Write-Host "`n> $texto" -ForegroundColor Magenta }
function Falha([string]$texto) { Write-Host "`nX $texto" -ForegroundColor Red; exit 1 }

# Comando nativo nao levanta excecao: so muda o $LASTEXITCODE. Entao toda
# chamada que precisa dar certo passa por aqui.
function Rode([string]$exe, [string[]]$argumentos) {
  & $exe @argumentos
  if ($LASTEXITCODE -ne 0) {
    Falha ("$exe " + ($argumentos -join " ") + " falhou (codigo $LASTEXITCODE)")
  }
}

# E a que PODE dar errado passa por aqui: devolve o codigo e engole o que for
# escrito no stderr, que com ErrorActionPreference=Stop viraria excecao.
function Codigo([string]$exe, [string[]]$argumentos) {
  $antes = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $exe @argumentos 2>&1 | Out-Null
    return $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $antes
  }
}

# --- Python ---------------------------------------------------------------
# `py` sem argumento escolhe o Python mais novo instalado; a checagem de
# versao e que decide se serve.
$pyExe = $null
foreach ($nome in @("py", "python", "python3")) {
  $cmd = Get-Command $nome -ErrorAction SilentlyContinue
  if (-not $cmd) { continue }
  $teste = @("-c", "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)")
  if ((Codigo $cmd.Source $teste) -eq 0) { $pyExe = $cmd.Source; break }
}
if (-not $pyExe) {
  Falha "Precisa de Python 3.12 ou mais novo. Instale com:  winget install Python.Python.3.13"
}

# --- Node -----------------------------------------------------------------
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
  Falha "Precisa do Node.js, que traz o npm. Instale com:  winget install OpenJS.NodeJS.LTS"
}

# --- venv -----------------------------------------------------------------
$vpy = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) {
  Passo "Criando o ambiente virtual em .venv"
  Rode $pyExe @("-m", "venv", ".venv")
}
# Venv criada pelo `uv venv` nao tem pip, e o README antigo mandava usar uv.
if ((Codigo $vpy @("-m", "pip", "--version")) -ne 0) {
  Passo "O .venv nao tem pip - instalando"
  if ((Codigo $vpy @("-m", "ensurepip", "--upgrade")) -ne 0) {
    Rode $pyExe @("-m", "venv", "--upgrade", ".venv")
  }
}

Passo "Instalando as dependencias Python"
Rode $vpy @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
Rode $vpy @("-m", "pip", "install", "--quiet", "-e", ".[dev,api]")

# --- banco ----------------------------------------------------------------
if ((Codigo $vpy @("-m", "ingest", "ping")) -eq 0) {
  Passo "Postgres ja esta respondendo"
} else {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  $dockerVivo = $docker -and ((Codigo $docker.Source @("info")) -eq 0)
  if ($dockerVivo) {
    Passo "Subindo o Postgres pelo docker compose"
    Rode $docker.Source @("compose", "up", "-d", "db")
    Rode $vpy @("-m", "ingest", "ping", "--espera", "90")
  } else {
    Falha @"
Nenhum Postgres respondendo, e o Docker Desktop nao esta no ar.

  Saida 1 - Docker ja instalado: abra o Docker Desktop, espere a baleia
    ficar verde e rode isto de novo. O docker-compose.yml ja tem o banco.

  Saida 2 - Postgres nativo, sem Docker (roda como servico do Windows,
    sobe sozinho com a maquina):

      winget install PostgreSQL.PostgreSQL.16

    Depois crie o usuario e o banco que o projeto espera - ele vai pedir a
    senha do superusuario que voce escolheu na instalacao:

      & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres ``
        -c "create role vaster login password 'vaster' createdb" ``
        -c "create database vaster owner vaster"

  Saida 3 - ja tem um Postgres 16 em algum lugar: aponte a variavel e rode
    de novo.

      `$env:VASTER_DB_DSN = "postgresql://usuario:senha@localhost:5432/vaster"
"@
  }
}

Passo "Aplicando as migrations"
Rode $vpy @("-m", "ingest", "migrate")

# --- catalogo -------------------------------------------------------------
if (-not $SoTela) {
  $slots = 0
  foreach ($linha in (& $vpy -m ingest saude)) {
    if ($linha -match "^slots\s+(\d+)") { $slots = [int]$Matches[1] }
  }
  if ($slots -gt 0) {
    Passo "O catalogo ja tem $slots slots - pegando so o que entrou de novo"
    Rode $vpy @("-m", "ingest", "update")
  } elseif ($Rapido) {
    Passo "Montando o catalogo ocidental (ingles e portugues)"
    Rode $vpy @("-m", "ingest", "species", "--sem-ja")
    Rode $vpy @("-m", "ingest", "sets", "--region", "west")
    Rode $vpy @("-m", "ingest", "cards", "--region", "west")
    Rode $vpy @("-m", "ingest", "details", "--all", "--bulk", "--region", "west")
    Rode $vpy @("-m", "ingest", "links", "--all")
    Rode $vpy @("-m", "ingest", "slots", "--all", "--region", "west")
  } else {
    Passo "Montando o catalogo inteiro - uns 7 minutos, o japones e carta por carta"
    Rode $vpy @("-m", "ingest", "species")
    Rode $vpy @("-m", "ingest", "sets")
    Rode $vpy @("-m", "ingest", "cards")
    Rode $vpy @("-m", "ingest", "details", "--all", "--bulk")
    Rode $vpy @("-m", "ingest", "links", "--all")
    Rode $vpy @("-m", "ingest", "slots", "--all")
  }
  Rode $vpy @("-m", "ingest", "saude")
}

# --- tela -----------------------------------------------------------------
Set-Location (Join-Path $raiz "web\app")
if (-not (Test-Path "node_modules")) {
  Passo "Instalando as dependencias do frontend"
  Rode $npm.Source @("install")
}
if (-not $Dev) {
  Passo "Compilando a tela"
  Rode $npm.Source @("run", "build")
}
Set-Location $raiz

if ($Dev) {
  Passo "API numa janela nova, em :$Porta. A tela abre em http://127.0.0.1:5173"
  Start-Process -FilePath $vpy -WorkingDirectory $raiz `
    -ArgumentList @("-m", "uvicorn", "api.main:app", "--reload", "--port", "$Porta")
  Set-Location (Join-Path $raiz "web\app")
  Rode $npm.Source @("run", "dev")
} else {
  Passo "Pronto. Abra http://127.0.0.1:$Porta  (Ctrl+C para parar)"
  Rode $vpy @("-m", "uvicorn", "api.main:app", "--port", "$Porta")
}
