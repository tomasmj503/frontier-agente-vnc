#!/usr/bin/env bash
# Publica la versión más reciente del agente. Se corre EN EL SERVIDOR, dentro de la carpeta
# del proyecto (donde está este archivo y el .env):
#
#     ./deploy.sh
#
# Hace: bajar el código nuevo (git pull) -> armar la imagen (docker build) -> reemplazar el
# contenedor -> comprobar /health. Caddy llega al contenedor por la red de Docker
# (frontier-api:8000); el puerto de PUBLICAR es solo para comprobar desde el propio servidor.
#
# Ajustes opcionales (variables de entorno):
#   NOMBRE=frontier-api         nombre del contenedor y de la imagen (Caddy apunta a este nombre)
#   PUBLICAR=127.0.0.1:8010     puerto del servidor desde donde se comprueba /health
#   RED=jutilabs_default        red de Docker donde vive Caddy ("" para no usar red)
#   INTENTOS=40                 cuántas veces probar /health al arrancar (1 por segundo)
set -euo pipefail
cd "$(dirname "$0")"

NOMBRE="${NOMBRE:-frontier-api}"
PUBLICAR="${PUBLICAR:-127.0.0.1:8010}"
RED="${RED-jutilabs_default}"
INTENTOS="${INTENTOS:-40}"

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

echo "== 4/4 Comprobando /health (hasta $INTENTOS intentos)"
TOKEN="$(grep '^TEAM_TOKEN=' .env | cut -d= -f2-)"
# Bucle propio: reintenta ante cualquier falla mientras arranca (conexión rechazada, conexión
# cortada, respuesta vacía o error 5xx). curl --retry no cubre la conexión cortada.
for i in $(seq 1 "$INTENTOS"); do
  if resp="$(curl -fsS -m 3 -H "Authorization: Bearer $TOKEN" "http://$PUBLICAR/health" 2>/dev/null)"; then
    echo "$resp"
    echo "Listo (intento $i): $(git log --oneline -1)"
    exit 0
  fi
  sleep 1
done

echo "El servicio no respondió tras $INTENTOS intentos. Últimas líneas del log:"
docker logs --tail 20 "$NOMBRE"
exit 1
