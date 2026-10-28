#!/usr/bin/env bash
# Roda os testes PUBLICOS contra o container do aluno.
# Uso: bash scripts/rodar_testes.sh   (requer Docker + python3 + pytest)
#
# Dois modos (mesma regra da suite escondida da correcao):
#   - compose.yaml CUSTOMIZADO (sha256 != do template registrado no
#     track.json): sobe o ambiente com `docker compose up --build -d`;
#   - compose.yaml intacto ou ausente: sobe so o Containerfile.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: docker nao encontrado." >&2
  exit 2
fi

python3 scripts/variante.py >/dev/null
# PORTA_API vem da variante do repo (fallback 9201 — mesmo default do sistema)
PORTA=$(python3 -c "import json,os;p='variante/params.json';print(json.load(open(p)).get('PORTA_API',9201) if os.path.exists(p) else 9201)")
SLUG=$(python3 -c "import json;print(json.load(open('variante/params.json'))['slug'])")
# printf '%s' (sem \n do echo): evita trailing '-' invalido na tag do docker
SUF=$(printf '%s' "$SLUG" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/-*$//')
IMAGEM="prova-$SUF"

# Modo compose: compose.yaml existe E foi customizado pelo aluno
COMPOSE_MODE=$(python3 - <<'PY'
import hashlib, json, os
try:
    tj = json.load(open("track.json", encoding="utf-8"))
    tsha = tj.get("compose", {}).get("template_sha256", "")
    ok = bool(tsha) and os.path.exists("compose.yaml") and \
        hashlib.sha256(open("compose.yaml", "rb").read()).hexdigest() != tsha
except Exception:
    ok = False
print(1 if ok else 0)
PY
)

aguarda() {
  for i in $(seq 1 40); do
    if curl -fsS "http://localhost:$PORTA/healthz" >/dev/null 2>&1; then
      return 0
    fi
    if [ "$i" = "40" ]; then
      echo "ERRO: API nao respondeu /healthz a tempo." >&2
      return 1
    fi
    sleep 2
  done
}

if [ "$COMPOSE_MODE" = "1" ]; then
  PROJ="prova-teste-$SUF"
  echo "==> compose.yaml customizado detectado — subindo via docker compose"
  if ! docker compose version >/dev/null 2>&1; then
    echo "ERRO: 'docker compose' indisponivel (plugin compose ausente)." >&2
    exit 2
  fi
  PORTA_API="$PORTA" docker compose -f compose.yaml -p "$PROJ" down -v >/dev/null 2>&1 || true
  PORTA_API="$PORTA" docker compose -f compose.yaml -p "$PROJ" up --build -d

  cleanup() {
    PORTA_API="$PORTA" docker compose -f compose.yaml -p "$PROJ" down -v >/dev/null 2>&1 || true
  }
  trap cleanup EXIT

  if ! aguarda; then
    PORTA_API="$PORTA" docker compose -f compose.yaml -p "$PROJ" logs --tail=50 >&2 || true
    exit 1
  fi

  echo "==> pytest (testes publicos)"
  BASE_URL="http://localhost:$PORTA" REPO_SLUG="$SLUG" \
    python3 -m pytest tests/public -q --tb=short
  exit 0
fi

# Modo single-container (compose.yaml intacto ou ausente)
CONTAINERFILE="Dockerfile"
[ -f Containerfile ] && CONTAINERFILE="Containerfile"

echo "==> build $IMAGEM (de $CONTAINERFILE)"
docker build -q -t "$IMAGEM" -f "$CONTAINERFILE" .

echo "==> subindo em localhost:$PORTA"
docker rm -f "prova-teste-$SUF" >/dev/null 2>&1 || true
docker run -d --name "prova-teste-$SUF" -p "$PORTA:8080" "$IMAGEM" >/dev/null

cleanup() { docker rm -f "prova-teste-$SUF" >/dev/null 2>&1 || true; }
trap cleanup EXIT

if ! aguarda; then
  docker logs "prova-teste-$SUF" >&2 || true
  exit 1
fi

echo "==> pytest (testes publicos)"
BASE_URL="http://localhost:$PORTA" REPO_SLUG="$SLUG" \
  python3 -m pytest tests/public -q --tb=short
