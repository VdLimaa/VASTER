#!/usr/bin/env bash
# Sobe o Masterset BR em localhost: banco, ingestão e tela.
#
#   scripts/subir.sh              # catálogo inteiro (~7 min) e a tela em :8000
#   scripts/subir.sh --rapido     # só en/pt, ~1 min — é o que importa primeiro
#   scripts/subir.sh --dev        # dois processos, com recarga instantânea
#   scripts/subir.sh --so-tela    # pula a ingestão
#
# O gêmeo em PowerShell é scripts/subir.ps1. Os dois fazem os mesmos passos,
# na mesma ordem, e a espera pelo banco mora em `python -m ingest ping` para
# não existir um laço de retentativa em bash e outro em PowerShell.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

RAPIDO=0
DEV=0
SO_TELA=0
PORTA=8000

while [ $# -gt 0 ]; do
  case "$1" in
    --rapido)  RAPIDO=1 ;;
    --dev)     DEV=1 ;;
    --so-tela) SO_TELA=1 ;;
    --porta)   PORTA="${2:?--porta precisa de um número}"; shift ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
  shift
done

passo() { printf '\n\033[1;35m▸ %s\033[0m\n' "$1"; }
falha() { printf '\n\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# --- Python ---------------------------------------------------------------
PY=""
for cand in python3.13 python3.12 python3 python; do
  if command -v "$cand" >/dev/null 2>&1 &&
     "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || falha "Precisa de Python 3.12 ou mais novo. No macOS: brew install python@3.13. No Debian/Ubuntu: sudo apt install python3.13-venv"

# --- Node -----------------------------------------------------------------
command -v npm >/dev/null 2>&1 || falha "Precisa do Node.js (que traz o npm): https://nodejs.org"

# --- venv -----------------------------------------------------------------
VPY="$RAIZ/.venv/bin/python"
if [ ! -x "$VPY" ]; then
  passo "Criando o ambiente virtual em .venv"
  "$PY" -m venv .venv
fi
# Venv criada pelo `uv venv` não tem pip, e o README antigo mandava usar uv.
if ! "$VPY" -m pip --version >/dev/null 2>&1; then
  passo "O .venv não tem pip — instalando"
  "$VPY" -m ensurepip --upgrade >/dev/null 2>&1 || "$PY" -m venv --upgrade .venv
fi

passo "Instalando as dependências Python"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -e '.[dev,api]'

# --- banco ----------------------------------------------------------------
if "$VPY" -m ingest ping >/dev/null 2>&1; then
  passo "Postgres já está respondendo"
else
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    passo "Subindo o Postgres pelo docker compose"
    docker compose up -d db
    "$VPY" -m ingest ping --espera 90 || falha "O container subiu mas o Postgres não respondeu em 90s. Olhe 'docker compose logs db'"
  else
    falha "Nenhum Postgres respondendo, e o Docker não está disponível.

  Saída 1 — Docker instalado: suba o serviço e rode isto de novo. O
    docker-compose.yml deste repositório já tem o banco pronto.

  Saída 2 — Postgres nativo, sem Docker. Instale o 16 e crie o usuário e o
    banco que o projeto espera:

      sudo -u postgres psql \\
        -c \"create role vaster login password 'vaster' createdb\" \\
        -c 'create database vaster owner vaster'

  Saída 3 — já tem um Postgres 16: aponte a variável e rode de novo.

      export VASTER_DB_DSN=postgresql://usuario:senha@localhost:5432/vaster"
  fi
fi

passo "Aplicando as migrations"
"$VPY" -m ingest migrate

# --- catálogo -------------------------------------------------------------
if [ "$SO_TELA" = 0 ]; then
  SLOTS="$("$VPY" -m ingest saude | awk '/^slots /{print $2}')"
  if [ "${SLOTS:-0}" -gt 0 ]; then
    passo "O catálogo já tem $SLOTS slots — pegando só o que entrou de novo"
    "$VPY" -m ingest update
  elif [ "$RAPIDO" = 1 ]; then
    passo "Montando o catálogo ocidental (inglês e português)"
    "$VPY" -m ingest species --sem-ja
    "$VPY" -m ingest sets   --region west
    "$VPY" -m ingest cards  --region west
    "$VPY" -m ingest details --all --bulk --region west
    "$VPY" -m ingest links --all
    "$VPY" -m ingest slots --all --region west
  else
    passo "Montando o catálogo inteiro — uns 7 minutos, o japonês é carta por carta"
    "$VPY" -m ingest species
    "$VPY" -m ingest sets
    "$VPY" -m ingest cards
    "$VPY" -m ingest details --all --bulk
    "$VPY" -m ingest links --all
    "$VPY" -m ingest slots --all
  fi
  "$VPY" -m ingest saude
fi

# --- tela -----------------------------------------------------------------
cd web/app
[ -d node_modules ] || { passo "Instalando as dependências do frontend"; npm install; }
if [ "$DEV" = 0 ]; then
  passo "Compilando a tela"
  npm run build
fi
cd "$RAIZ"

if [ "$DEV" = 1 ]; then
  passo "API em http://127.0.0.1:$PORTA  ·  tela em http://127.0.0.1:5173"
  "$VPY" -m uvicorn api.main:app --reload --port "$PORTA" &
  API=$!
  trap 'kill $API 2>/dev/null || true' EXIT
  cd web/app && exec npm run dev
else
  passo "Pronto: http://127.0.0.1:$PORTA"
  exec "$VPY" -m uvicorn api.main:app --port "$PORTA"
fi
