#!/usr/bin/env bash
# descrizione

set -e  # Interrompe lo script in caso di errori

# mi porto nella cartella dello script
cd /home/userradio2
# carico le variabili dal file .env
set -a
source .env
set +a

# creo la cartella se non esiste
LOCAL_DIR="${WEBVIEW_EXPORT_PATH}/export"
mkdir -p "$LOCAL_DIR" 

python3 ./transform_file.py

lftp -u "${FTPS_USER},${FTPS_PASS}" -p "${FTPS_PORT}" "${FTPS_HOST}" <<EOF
# Impostazioni SSL/TLS
set ftp:ssl-force true
set ftp:ssl-protect-data true

# Se il server usa un certificato autofirmato o non riconosciuto, scommenta la riga seguente:
set ssl:verify-certificate no

# Timeout e tentativi di connessione
set net:timeout 15
set net:max-retries 3

# Crea la cartella remota se non esiste
# mkdir -p "${FTP_REMOTE_DIR}"

# Sincronizza i file dalla cartella locale alla cartella remota
# -R: Reverse mirror (upload da locale a remoto)
# --only-newer: Carica solo i file nuovi o modificati
mirror -R --only-newer --Remove-source-files "${LOCAL_DIR}" "${REMOTE_DIR}"

# Termina la sessione
quit
EOF

echo "caricamento terminato"

rm -rf "$LOCAL_DIR"

echo "cartella export eliminata"
