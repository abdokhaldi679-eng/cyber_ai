# CyberAI - Framework IA de Cybersécurité

**AI-puissance : L'intelligence artificielle au service de la cybersécurité**

CyberAI est un framework modulaire tout-en-un qui combine l'apprentissage automatique avec des techniques de cybersécurité classiques pour offrir une suite complète d'outils de sécurité.

## Fonctionnalités

| Module | Description | Technologie |
|--------|-------------|-------------|
| **IDS** | Détection d'intrusion réseau | Isolation Forest / Random Forest |
| **Malware** | Classification et analyse de malwares | Gradient Boosting + analyse statique |
| **Scan** | Scan de ports et vulnérabilités | Multithreading + analyses heuristiques |
| **Phishing** | Détection d'URLs de phishing | Random Forest + analyse de features |
| **Logs** | Analyse de logs et détection d'attaques | Pattern matching + corrélation |
| **Password** | Analyse et génération de mots de passe | Calcul d'entropie + HIBP API |
| **Web** | Scanner web (XSS, SQLi, etc.) | BeautifulSoup + tests de payloads |

## Installation

```bash
git clone https://github.com/tonuser/cyber_ai.git
cd cyber_ai
pip install -r requirements.txt
```

## Utilisation

```bash
# Aide générale
python main.py help

# Détection d'intrusion réseau
python main.py ids

# Analyser un fichier suspect
python main.py malware -f fichier.exe

# Scanner les ports d'une cible
python main.py scan 192.168.1.1 --quick

# Scanner les vulnérabilités
python main.py scan example.com --vuln

# Détecter un phishing
python main.py phishing -u https://example.com

# Analyser des logs
python main.py logs -f access.log

# Analyser un mot de passe
python main.py password -p "monMotDePasse123"

# Générer un mot de passe sécurisé
python main.py password --generate --length 25

# Scanner un site web
python main.py web https://example.com

# Analyse complète (tout-en-un)
python main.py all example.com
```

## Tests

```bash
python -m pytest tests/ -v
```

## Architecture

```
cyber_ai/
├── main.py              # CLI principal
├── ids/                 # Détection d'intrusion
│   ├── intrusion_detector.py  # Modèle ML
│   └── network_monitor.py     # Surveillance réseau
├── malware/             # Analyse de malwares
│   ├── classifier.py    # Classification ML
│   └── analyzer.py      # Analyse statique
├── scanner/             # Scan
│   ├── port_scanner.py  # Scan de ports
│   └── vulnerability_scanner.py  # Vulnérabilités
├── phishing/            # Détection de phishing
│   └── detector.py      # Classification ML
├── analysis/            # Analyse
│   ├── log_analyzer.py  # Analyse de logs
│   └── password_analyzer.py  # Analyse de mots de passe
├── web/                 # Scanner web
│   └── web_scanner.py   # Crawler + tests
├── utils/               # Utilitaires
│   └── helpers.py       # Fonctions communes
└── tests/               # Tests unitaires
```

## Sécurité

- Utilisation de modèles ML entraînés sur des données synthétiques
- Vérification des mots de passe via l'API Have I Been Pwned (K-anonymity)
- Aucune donnée personnelle collectée

## Licence

MIT License
