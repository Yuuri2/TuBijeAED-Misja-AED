#!/usr/bin/env bash
# Uruchomienie prototypu #TuBijeAED na localhost (Linux/macOS).
#   ./uruchom.sh           – start na http://localhost:8080/jury.html
#   ./uruchom.sh --reset   – najpierw usuwa bazę demo i pliki z data/ (świeży seed)
#   BEZ_PRZEGLADARKI=1     – nie otwieraj przeglądarki
set -euo pipefail
KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$KORZEN/2_prototyp_kod"
VENV="$KORZEN/.venv"
PORT=8080
URL="http://localhost:$PORT/jury.html"

if [ "${1:-}" = "--reset" ]; then
  echo ">> Reset: usuwam bazę demo i pliki z $APP/data/ ..."
  rm -rf "$APP/data"
  mkdir -p "$APP/data"
fi

PY=""
for kand in python3 python; do
  if command -v "$kand" >/dev/null 2>&1 && "$kand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    PY="$kand"; break
  fi
done
if [ -z "$PY" ]; then
  echo "BŁĄD: potrzebny jest Python 3.11 lub nowszy (python3 --version). Zainstaluj go z https://www.python.org/downloads/" >&2
  exit 1
fi
echo ">> Python: $($PY --version)"

if [ ! -x "$VENV/bin/python" ]; then
  echo ">> Tworzę środowisko wirtualne w $VENV ..."
  "$PY" -m venv "$VENV" || { echo "BŁĄD: nie udało się utworzyć .venv (na Debianie/Ubuntu: sudo apt install python3-venv)" >&2; exit 1; }
fi

echo ">> Instaluję zależności (pierwsze uruchomienie może potrwać) ..."
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$APP/requirements.txt" \
  || { echo "BŁĄD: instalacja zależności nie powiodła się (sprawdź połączenie z internetem)." >&2; exit 1; }

if "$VENV/bin/python" - "$PORT" <<'PYEOF'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
PYEOF
then :; else
  echo "BŁĄD: port $PORT jest zajęty. Zamknij działający serwer i spróbuj ponownie." >&2
  exit 1
fi

if [ -z "${BEZ_PRZEGLADARKI:-}" ]; then
  (
    sleep 3
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 || true
    else echo ">> Nie znaleziono xdg-open/open – otwórz ręcznie: $URL"; fi
  ) &
fi

echo ">> Start serwera: $URL   (Ctrl+C zatrzymuje)"
cd "$APP"
exec "$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
