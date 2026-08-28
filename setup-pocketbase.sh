#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# setup-pocketbase.sh
#
# Bequemer Wrapper für Termux: prüft, ob PocketBase erreichbar ist,
# installiert die npm-Abhängigkeiten (falls nötig) und führt dann
# scripts/pocketbase-setup.mjs aus, das alle Collections (Genres,
# Tags, Serien, Staffeln, Episoden, Filme, Bewertungen, Watchlist,
# Abos, Benachrichtigungen, Sammlungen, Forum, Tickets, Favoriten)
# sowie die Nutzerrollen anlegt bzw. aktualisiert.
#
# Aufruf im Projektordner (z.B. ~/animem):
#   bash setup-pocketbase.sh
# ============================================================

set -euo pipefail

# --- 1. Im Projektordner? -----------------------------------
if [ ! -f "scripts/pocketbase-setup.mjs" ]; then
  echo "Fehler: scripts/pocketbase-setup.mjs nicht gefunden."
  echo "Bitte dieses Skript im Projektordner ausführen, z.B.:"
  echo "  cd ~/animem && bash setup-pocketbase.sh"
  exit 1
fi

# --- 2. .env.local vorhanden? --------------------------------
if [ ! -f ".env.local" ]; then
  echo "Fehler: .env.local fehlt."
  echo "Bitte zuerst anlegen, z.B.:"
  cat << 'EOF'

  cat > .env.local << 'ENV'
  NEXT_PUBLIC_POCKETBASE_URL=http://127.0.0.1:8090
  POCKETBASE_ADMIN_EMAIL=deine@mail.tld
  POCKETBASE_ADMIN_PASSWORD=deinPasswort
  ANIMEM_IMAGE_HOSTS=
  ENV

EOF
  exit 1
fi

# Werte aus .env.local laden, um die Erreichbarkeit zu prüfen.
set -a
source .env.local
set +a

if [ -z "${NEXT_PUBLIC_POCKETBASE_URL:-}" ]; then
  echo "Fehler: NEXT_PUBLIC_POCKETBASE_URL ist in .env.local nicht gesetzt."
  exit 1
fi

# --- 3. Ist PocketBase erreichbar? ---------------------------
echo "Prüfe PocketBase unter ${NEXT_PUBLIC_POCKETBASE_URL} ..."
if ! curl -s -o /dev/null -w "" --max-time 5 "${NEXT_PUBLIC_POCKETBASE_URL}/api/health"; then
  echo "Fehler: PocketBase antwortet nicht unter ${NEXT_PUBLIC_POCKETBASE_URL}."
  echo "Läuft './pocketbase serve --http=0.0.0.0:8090' noch in der anderen Termux-Sitzung?"
  exit 1
fi
echo "PocketBase ist erreichbar."

# --- 4. npm-Abhängigkeiten installieren (nur falls nötig) ----
if [ ! -d "node_modules" ]; then
  echo "Installiere npm-Abhängigkeiten (kann etwas dauern) ..."
  npm install
else
  echo "node_modules bereits vorhanden, überspringe npm install."
  echo "(Falls package.json sich geändert hat: npm install manuell erneut ausführen.)"
fi

# --- 5. Collections/Rollen/Genres/etc. anlegen ----------------
echo ""
echo "Lege Collections in PocketBase an ..."
node scripts/pocketbase-setup.mjs

echo ""
echo "Fertig. Du kannst die Webseite jetzt starten mit:"
echo "  npm run dev"
