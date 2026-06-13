#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/abdokhaldi679-eng/cyber_ai.git"
INSTALL_DIR="$HOME/cyber_ai"

echo "[+] Installation de CyberAI - Framework IA de Cybersécurité"
echo "[+] Utilisation de Python 3"

if ! command -v python3 &>/dev/null; then
    echo "[-] Python 3 n'est pas installé. Veuillez installer Python 3.8+"
    exit 1
fi

if [ -d "$INSTALL_DIR" ]; then
    echo "[+] Mise à jour de l'installation existante..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "[+] Clonage du dépôt..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo "[+] Installation des dépendances..."
pip3 install -r requirements.txt

echo "[+] Installation du package..."
pip3 install -e .

echo ""
echo "[+] CyberAI installé avec succès !"
echo "[+] Utilisation : cyber-ai help"
echo "[+] Exemple    : cyber-ai scan example.com --vuln"
