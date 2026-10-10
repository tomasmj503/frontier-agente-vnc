#!/usr/bin/env bash
# Publica la versión más reciente del agente. Se corre EN EL SERVIDOR, dentro de la carpeta
# del proyecto (donde está este archivo y el .env):
#
#     ./deploy.sh
#
# Hace: bajar el código nuevo (git pull) -> armar la imagen (docker build) -> reemplazar el
# contenedor -> comprobar /health. Caddy apunta a PUBLICAR (por defecto 127.0.0.1:8000).
#
# Ajustes opcionales (variables de entorno):
#   NOMBRE=frontier           nombre del contenedor y de la imagen
#   PUBLICAR=127.0.0.1:8000   dónde escucha en el servidor (a donde apunta Caddy)
#   RED=                      red de Docker de Caddy, si Caddy corre dentro de Docker
set -euo pipefail
cd "$(dirname "$0")"

NOMBRE="${NOMBRE:-frontier}"
PUBLICAR="${PUBLICAR:-127.0.0.1:8000}"
RED="${RED:-}"

[ -f .env ] || { echo "Falta el archivo .env en $(pwd). Cópialo desde la Mac con scp."; exit 1; }
command -v docker >/dev/null || { echo "Docker no está instalado."; exit 1; }

echo "== 1/4 Bajando el código nuevo"
git pull --ff-only

echo "== 2/4 Armando la imagen (la primera vez tarda unos minutos)"
docker build -t "$NOMBRE" .

echo "== 3/4 Reemplazando el contenedor"
docker rm -f "$NOMBRE" >/dev/null 2>&1 || true
mkdir -p logs
args=(-d --name "$NOMBRE" --restart unless-stopped --env-file .env -v "$PWD/logs:/srv/logs" -p "$PUBLICAR:8000")
if [ -n "$RED" ]; then args+=(--network "$RED"); fi
docker run "${args[@]}" "$NOMBRE" >/dev/null

echo "== 4/4 Comprobando /health"
TOKEN="$(grep '^TEAM_TOKEN=' .env | cut -d= -f2-)"
if curl -fsS --retry 20 --retry-connrefused --retry-delay 1 \
     -H "Authorization: Bearer $TOKEN" "http://$PUBLICAR/health"; then
  echo
  echo "Listo: $(git log --oneline -1)"
else
  echo
  echo "El servicio no respondió. Últimas líneas del log:"
  docker logs --tail 20 "$NOMBRE"
  exit 1
fi
