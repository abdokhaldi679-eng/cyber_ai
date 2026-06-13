#!/usr/bin/env python3
import sys
import os
import argparse
import json
from colorama import Fore, Style

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.helpers import banner, info, success, warning, error, resolve_domain
from ids.intrusion_detector import IntrusionDetector
from ids.network_monitor import NetworkMonitor
from malware.classifier import MalwareClassifier
from malware.analyzer import MalwareAnalyzer
from scanner.port_scanner import PortScanner
from scanner.vulnerability_scanner import VulnerabilityScanner
from phishing.detector import PhishingDetector
from analysis.log_analyzer import LogAnalyzer
from analysis.password_analyzer import PasswordAnalyzer
from web.web_scanner import WebScanner
from router.scanner import RouterScanner
from router.tplink_exploit import TPLinkExploit
from router.zte_exploit import ZTEExploit
from router.credential_bruteforce import CredentialBruteforce
from router.config_extractor import ConfigExtractor
from router.exploit_db import ExploitDB


def cmd_intrusion(args):
    detector = IntrusionDetector()
    monitor = NetworkMonitor()
    print(banner())
    info("Module Détection d'Intrusion (IDS/AI)")
    print("-" * 60)

    monitor.start()

    if args.analyze:
        det = IntrusionDetector()
        test_features = [
            10, 3, 500, 300, 50, 0.5, 0.2, 5, 2, 0.8, 0.1,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        ]
        result = det.analyze_connection(test_features)
        print(f"\nAnalyse de connexion: {result}")

    print(f"\nStatistiques: {json.dumps(monitor.get_stats(), indent=2)}")
    monitor.stop()


def cmd_malware(args):
    print(banner())
    info("Module Analyse de Malware (AI)")
    print("-" * 60)

    classifier = MalwareClassifier()
    analyzer = MalwareAnalyzer()

    if args.file:
        result = analyzer.analyze_file(args.file)
        if result:
            print(f"\n{Fore.CYAN}Rapport d'analyse:{Style.RESET_ALL}")
            print(f"  Fichier: {result['filename']}")
            print(f"  Taille: {result['size']} octets")
            print(f"  Type: {result['file_type']}")
            print(f"  Entropie: {result['entropy']}")
            print(f"  SHA256: {result['hashes']['sha256'][:32]}...")
            print(f"  Chaînes suspectes: {len(result['suspicious_strings'])}")
            print(f"  Score: {result['risk_score']}/100")
            verdict_color = Fore.RED if "CRITIQUE" in result['verdict'] else (
                Fore.YELLOW if "SUSPECT" in result['verdict'] else (
                    Fore.GREEN if "Benin" in result['verdict'] else Fore.WHITE
                )
            )
            print(f"  Verdict: {verdict_color}{result['verdict']}{Style.RESET_ALL}")

            if result['suspicious_strings']:
                print(f"\n  Chaînes suspectes détectées:")
                for s in result['suspicious_strings'][:20]:
                    print(f"    - {s}")
    else:
        test_string = args.string or "hello world print function"
        result = classifier.analyze_strings(test_string)
        print(f"\nClassification de l'échantillon:")
        print(f"  Prédiction: {result['family']}")
        print(f"  Confiance: {result['confidence']:.2%}")
        print(f"  Malveillant: {Fore.RED if result['is_malicious'] else Fore.GREEN}{result['is_malicious']}{Style.RESET_ALL}")


def cmd_scan(args):
    print(banner())
    info("Module Scan de Ports et Vulnérabilités")
    print("-" * 60)

    target = args.target
    if not target:
        target = input("Cible (IP/domaine): ").strip()

    if args.vuln:
        scanner = VulnerabilityScanner(target)
        results = scanner.scan()

        print(f"\n{Fore.CYAN}Rapport de vulnérabilités pour {target}:{Style.RESET_ALL}")
        summary = scanner.generate_summary()
        risk_color = Fore.RED if summary['risk_level'] == "CRITICAL" else (
            Fore.YELLOW if summary['risk_level'] == "HIGH" else (
                Fore.MAGENTA if summary['risk_level'] == "MEDIUM" else Fore.GREEN
            )
        )
        print(f"  Score de risque: {summary['score']} ({risk_color}{summary['risk_level']}{Style.RESET_ALL})")
        print(f"  Vulnérabilités: {summary['vulnerability_count']}")

        if results:
            for v in results:
                sev_color = Fore.RED if v['severity'] == "CRITICAL" else (
                    Fore.YELLOW if v['severity'] == "HIGH" else (
                        Fore.MAGENTA if v['severity'] == "MEDIUM" else Fore.BLUE
                    )
                )
                print(f"\n  [{sev_color}{v['severity']}{Style.RESET_ALL}] {v['name']}")
                print(f"    Description: {v['description']}")
                print(f"    Remédiation: {v['remediation']}")
    else:
        scanner = PortScanner(target)

        if args.full:
            results = scanner.full_scan()
        elif args.quick:
            results = scanner.quick_scan()
        else:
            results = scanner.common_scan()

        if results:
            print(f"\n{Fore.CYAN}Ports ouverts sur {target}:{Style.RESET_ALL}")
            for p in results:
                risk_color = Fore.RED if p['risk'] == "HAUT" else (
                    Fore.YELLOW if p['risk'] == "MOYEN" else Fore.GREEN
                )
                print(f"  {p['port']:>5}/TCP  {p['service']:<15} [{risk_color}{p['risk']}{Style.RESET_ALL}]")
                if p['banner']:
                    print(f"         Bannière: {p['banner'][:80]}")

            summary = scanner.get_summary()
            print(f"\nRésumé:")
            print(f"  Total ouverts: {summary['total_open']}")
            print(f"  Haut risque: {summary['high_risk']}")
            print(f"  Services: {', '.join(summary['services'][:5])}")


def cmd_phishing(args):
    print(banner())
    info("Module Détection de Phishing (AI)")
    print("-" * 60)

    detector = PhishingDetector()

    if args.url:
        result = detector.analyze_domain(args.url)
        print(f"\nAnalyse de l'URL:")
        print(f"  URL: {result['url']}")
        status = Fore.RED if result['is_phishing'] else Fore.GREEN
        print(f"  Phishing: {status}{result['is_phishing']}{Style.RESET_ALL}")
        print(f"  Confiance: {result['confidence']:.2%}")
        print(f"  Score de risque: {result['risk_score']:.2%}")

        if result.get('risk_factors'):
            print(f"\n  {Fore.YELLOW}Facteurs de risque:{Style.RESET_ALL}")
            for reason in result['risk_factors']:
                print(f"    - {reason}")

        features = result.get('features', {})
        if features:
            print(f"\n  Caractéristiques:")
            print(f"    Longueur URL: {features['url_length']}")
            print(f"    Utilise IP: {features['has_ip']}")
            print(f"    HTTPS: {features['has_https']}")
            print(f"    TLD suspect: {features['suspicious_tld']}")
            print(f"    Mots-clés suspects: {features['suspicious_keywords']}")
    else:
        urls = [
            "https://www.google.com",
            "http://secure-login.xyz/verify/account",
            "https://github.com/login",
            "http://paypa1.com.security-update.tk/",
        ]
        for url in urls:
            result = detector.analyze_domain(url)
            icon = Fore.RED + "!" if result['is_phishing'] else Fore.GREEN + "+"
            print(f"  [{icon}{Style.RESET_ALL}] {url}")
            print(f"         -> {'PHISHING' if result['is_phishing'] else 'Sûr'} "
                  f"(confiance: {result['confidence']:.2%})")


def cmd_logs(args):
    print(banner())
    info("Module Analyse de Logs (AI)")
    print("-" * 60)

    analyzer = LogAnalyzer()

    if args.file:
        try:
            with open(args.file, "r") as f:
                content = f.read()
            analyzer.load_log(content)
        except FileNotFoundError:
            error(f"Fichier introuvable: {args.file}")
            return
    else:
        sample_logs = """192.168.1.100 - - [01/Jan/2024:10:30:15 +0000] "POST /login HTTP/1.1" 401 128
192.168.1.100 - - [01/Jan/2024:10:30:16 +0000] "POST /login HTTP/1.1" 401 128
192.168.1.100 - - [01/Jan/2024:10:30:17 +0000] "POST /login HTTP/1.1" 401 128
10.0.0.50 - - [01/Jan/2024:10:31:00 +0000] "GET /etc/passwd HTTP/1.1" 404 150
10.0.0.50 - - [01/Jan/2024:10:31:01 +0000] "GET /../../../etc/passwd HTTP/1.1" 404 150
192.168.1.200 - - [01/Jan/2024:10:32:00 +0000] "GET /products?id=1 UNION SELECT 1,2,3 HTTP/1.1" 200 500
192.168.1.200 - - [01/Jan/2024:10:32:01 +0000] "GET /search?q=<script>alert(1)</script> HTTP/1.1" 200 300
203.0.113.5 - - [01/Jan/2024:10:33:00 +0000] "POST /wp-login.php HTTP/1.1" 200 500
203.0.113.5 - - [01/Jan/2024:10:33:01 +0000] "POST /wp-login.php HTTP/1.1" 200 500
203.0.113.5 - - [01/Jan/2024:10:33:02 +0000] "POST /wp-login.php HTTP/1.1" 200 500"""
        analyzer.load_log(sample_logs)

    report = analyzer.generate_report()

    if report:
        risk_color = Fore.RED if report['risk_level'] == "CRITICAL" else (
            Fore.YELLOW if report['risk_level'] == "HIGH" else (
                Fore.MAGENTA if report['risk_level'] == "MEDIUM" else Fore.GREEN
            )
        )
        print(f"\n{Fore.CYAN}Rapport d'analyse des logs:{Style.RESET_ALL}")
        print(f"  Lignes analysées: {report['total_logs']}")
        print(f"  IPs uniques: {report['unique_ips']}")
        print(f"  Alertes: {report['alerts_count']}")
        print(f"  Score de menace: {report['threat_score']}")
        print(f"  Niveau de risque: {risk_color}{report['risk_level']}{Style.RESET_ALL}")

        if report.get('top_attackers'):
            print(f"\n  {Fore.YELLOW}Top attaquants:{Style.RESET_ALL}")
            for attacker in report['top_attackers']:
                print(f"    IP: {attacker['ip']} ({attacker['count']} requêtes)")

        if report.get('attack_types'):
            print(f"\n  {Fore.YELLOW}Types d'attaques:{Style.RESET_ALL}")
            for attack, count in report['attack_types'].items():
                print(f"    {attack}: {count}")


def cmd_password(args):
    print(banner())
    info("Module Analyse de Mots de Passe (AI)")
    print("-" * 60)

    analyzer = PasswordAnalyzer()

    if args.generate:
        print(f"\n{Fore.CYAN}Génération de mot de passe sécurisé:{Style.RESET_ALL}")
        pwd = analyzer.generate_password(args.length)
        print(f"  Mot de passe: {Fore.GREEN}{pwd}{Style.RESET_ALL}")
        analysis = analyzer.analyze(pwd)
        print(f"  Force: {analysis['strength']}")
        print(f"  Score: {analysis['score']}/100")
        print(f"  Entropie: {analysis['entropy']} bits")
        print(f"  Temps de craquage (offline): {analysis['crack_time']['offline']}")

        breach = analyzer.check_breach(pwd)
        if breach['is_breached']:
            print(f"  {Fore.RED}Attention: Ce mot de passe a été compromis {breach['breach_count']} fois!{Style.RESET_ALL}")
        return

    password = args.password
    if not password:
        password = input("Mot de passe à analyser: ").strip()

    result = analyzer.analyze(password)

    score_color = Fore.GREEN if result['score'] >= 80 else (
        Fore.YELLOW if result['score'] >= 60 else (
            Fore.MAGENTA if result['score'] >= 40 else Fore.RED
        )
    )

    print(f"\n{Fore.CYAN}Analyse du mot de passe:{Style.RESET_ALL}")
    print(f"  Masqué: {result['password']}")
    print(f"  Longueur: {result['length']} caractères")
    print(f"  Score: {score_color}{result['score']}/100{Style.RESET_ALL}")
    print(f"  Force: {score_color}{result['strength']}{Style.RESET_ALL}")
    print(f"  Entropie: {result['entropy']} bits")
    print(f"  Commun: {Fore.RED if result['is_common'] else Fore.GREEN}{result['is_common']}{Style.RESET_ALL}")

    print(f"\n  Temps estimé pour craquer:")
    print(f"    En ligne: {result['crack_time']['online']}")
    print(f"    Hors ligne: {result['crack_time']['offline']}")

    if result.get('patterns'):
        print(f"\n  {Fore.YELLOW}Motifs détectés:{Style.RESET_ALL}")
        for p in result['patterns']:
            print(f"    - {p}")

    if result.get('feedback'):
        print(f"\n  {Fore.YELLOW}Recommandations:{Style.RESET_ALL}")
        for fb in result['feedback']:
            print(f"    - {fb}")

    breach = analyzer.check_breach(password)
    print(f"\n  Vérification de fuite (Have I Been Pwned):")
    if breach['is_breached']:
        print(f"    {Fore.RED}COMPROMIS! ({breach['breach_count']} fois){Style.RESET_ALL}")
    else:
        print(f"    {Fore.GREEN}Aucune fuite connue{Style.RESET_ALL}")


def cmd_web(args):
    print(banner())
    info("Module Scan Web (AI)")
    print("-" * 60)

    url = args.url
    if not url:
        url = input("URL cible: ").strip()

    scanner = WebScanner(url)

    if args.sqli:
        results = scanner.check_sql_injection(url)
        if results:
            print(f"\n{Fore.RED}SQL Injection détectée!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}Aucune SQL Injection détectée{Style.RESET_ALL}")
    elif args.xss:
        results = scanner.check_xss(url)
        if results:
            print(f"\n{Fore.RED}XSS détectée!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}Aucune XSS détectée{Style.RESET_ALL}")
    else:
        results = scanner.scan(url, args.depth)

        summary = scanner.generate_summary()
        risk_color = Fore.RED if summary['risk_level'] == "CRITICAL" else (
            Fore.YELLOW if summary['risk_level'] == "HIGH" else (
                Fore.MAGENTA if summary['risk_level'] == "MEDIUM" else Fore.GREEN
            )
        )

        print(f"\n{Fore.CYAN}Rapport de scan web:{Style.RESET_ALL}")
        print(f"  Score de sécurité: {summary['score']} ({risk_color}{summary['risk_level']}{Style.RESET_ALL})")
        print(f"  URLs trouvées: {summary['urls_analyzed']}")
        print(f"  Formulaires: {summary['forms_analyzed']}")
        print(f"  Vulnérabilités: {summary['vulnerabilities_found']}")

        if results.get("technologies"):
            print(f"\n  Technologies détectées:")
            for tech_type, tech_name in results["technologies"]:
                print(f"    - {tech_type}: {tech_name}")

        if results.get("vulnerabilities"):
            print(f"\n  {Fore.YELLOW}Vulnérabilités:{Style.RESET_ALL}")
            for v in results["vulnerabilities"]:
                sev_color = Fore.RED if v['severity'] == "CRITICAL" else (
                    Fore.YELLOW if v['severity'] == "HIGH" else (
                        Fore.MAGENTA if v['severity'] == "MEDIUM" else Fore.BLUE
                    )
                )
                print(f"    [{sev_color}{v['severity']}{Style.RESET_ALL}] {v['type']}")
                print(f"      URL: {v.get('url', 'N/A')}")


def cmd_router(args):
    print(banner())
    info("Module Exploitation Routeurs (TP-Link / ZTE)")
    print("-" * 60)

    target_ip = args.target
    if not target_ip:
        target_ip = input("IP du routeur cible: ").strip()

    if args.discover:
        scanner = RouterScanner()
        subnet = args.subnet or "192.168.1.0/24"
        routers = scanner.quick_scan(subnet)
        if routers:
            print(f"\n{Fore.CYAN}Routeurs détectés:{Style.RESET_ALL}")
            for r in routers:
                brand_color = Fore.RED if r.get('brand') in ['TP-Link'] else (
                    Fore.YELLOW if r.get('brand') == 'ZTE' else Fore.WHITE
                )
                print(f"  {r['ip']:>15}:{r['port']:<5} {brand_color}{r.get('brand', '?'):<10}{Style.RESET_ALL} "
                      f"{r.get('model', '?'):<25} ports: {r.get('open_ports', [])}")
        return

    scanner = RouterScanner()
    router_info = scanner.scan_single(target_ip)

    if not router_info:
        error(f"Aucun routeur détecté sur {target_ip}")
        return

    print(f"\n{Fore.CYAN}Routeur détecté:{Style.RESET_ALL}")
    print(f"  IP: {router_info['ip']}")
    print(f"  Port: {router_info['port']}")
    print(f"  Marque: {router_info.get('brand', '?')}")
    print(f"  Modèle: {router_info.get('model', '?')}")
    print(f"  Firmware: {router_info.get('firmware', '?')}")
    print(f"  Ports ouverts: {router_info.get('open_ports', [])}")

    username = args.username or "admin"
    password = args.password or "admin"

    brand = router_info.get("brand", "").lower()

    if args.bruteforce:
        print(f"\n{Fore.CYAN}[Brute-force]{Style.RESET_ALL}")
        bf = CredentialBruteforce(router_info)
        if args.wordlist:
            results = bf.dictionary_attack(username, args.wordlist, args.threads)
        else:
            results = bf.brute_force(threads=args.threads)

        if results:
            print(f"\n{Fore.GREEN}Identifiants trouvés:{Style.RESET_ALL}")
            for r in results:
                print(f"  {r['username']}:{r['password']} (via {r['method']})")
        else:
            warning("Aucun identifiant valide trouvé")

    if brand == "tp-link":
        print(f"\n{Fore.CYAN}[Exploits TP-Link]{Style.RESET_ALL}")
        exploit = TPLinkExploit(router_info)
        results = exploit.run_all(username, password)

        if results:
            for r in results:
                sev_color = Fore.RED if r['severity'] == "CRITICAL" else (
                    Fore.YELLOW if r['severity'] == "HIGH" else Fore.MAGENTA
                )
                print(f"  [{sev_color}{r['severity']}{Style.RESET_ALL}] {r['exploit']}")
                print(f"         {r['description']}")

        if args.exploit:
            cmd = args.cmd or "id"
            result = exploit.exploit_rce(cmd)
            if result['success']:
                print(f"\n{Fore.GREEN}[RCE] Résultat:{Style.RESET_ALL}\n{result['output']}")

    elif brand == "zte":
        print(f"\n{Fore.CYAN}[Exploits ZTE]{Style.RESET_ALL}")
        exploit = ZTEExploit(router_info)
        results = exploit.run_all(username, password)

        if results:
            for r in results:
                sev_color = Fore.RED if r['severity'] == "CRITICAL" else (
                    Fore.YELLOW if r['severity'] == "HIGH" else Fore.MAGENTA
                )
                print(f"  [{sev_color}{r['severity']}{Style.RESET_ALL}] {r['exploit']}")
                print(f"         {r['description']}")

        if args.exploit:
            cmd = args.cmd or "id"
            result = exploit.exploit_rce(cmd)
            if result['success']:
                print(f"\n{Fore.GREEN}[RCE] Résultat:{Style.RESET_ALL}\n{result['output']}")

    else:
        warning(f"Marque '{router_info.get('brand', '?')}' non reconnue, test générique...")
        print(f"\n{Fore.CYAN}[Tests génériques]{Style.RESET_ALL}")

        bf = CredentialBruteforce(router_info)
        b_results = bf.brute_force(threads=args.threads)
        if b_results:
            for r in b_results:
                print(f"  Identifiants: {r['username']}:{r['password']}")

    if args.extract:
        print(f"\n{Fore.CYAN}[Extraction de configuration]{Style.RESET_ALL}")
        extractor = ConfigExtractor(router_info, username, password)
        config = extractor.extract_all()
        if config:
            print(f"  Configuration extraite avec succès")
            for section, data in config.items():
                print(f"    {section}: {type(data).__name__} ({len(str(data))} octets)")
            if args.output:
                import json
                with open(args.output, "w") as f:
                    json.dump(config, f, indent=2)
                success(f"  Configuration sauvegardée: {args.output}")

    if args.list_exploits:
        print(f"\n{Fore.CYAN}[Base d'exploits]{Style.RESET_ALL}")
        db = ExploitDB()
        if brand:
            exploits = db.search(brand=brand)
        else:
            exploits = db.search()
        summary = db.get_summary()
        print(f"  Total exploits: {summary['total_exploits']}")
        print(f"  CRITICAL: {summary['critical']}, HIGH: {summary['high']}, MEDIUM: {summary['medium']}")
        for exp in exploits[:10]:
            sev_color = Fore.RED if exp['severity'] == "CRITICAL" else Fore.YELLOW
            print(f"  [{sev_color}{exp['cve']}{Style.RESET_ALL}] {exp['type']} - {exp['description'][:80]}")


def cmd_all(args):
    print(banner())
    info("Mode TOUT-EN-UN - Analyse complète")
    print("=" * 60)

    target = args.target
    if not target:
        target = input("Cible (IP/domaine): ").strip()

    print(f"\n{Fore.CYAN}[1/5] Scan de ports...{Style.RESET_ALL}")
    scanner = PortScanner(target)
    ports = scanner.common_scan()
    print(f"  {len(ports)} ports ouverts trouvés")

    print(f"\n{Fore.CYAN}[2/5] Scan de vulnérabilités...{Style.RESET_ALL}")
    vuln_scanner = VulnerabilityScanner(target)
    vulns = vuln_scanner.scan()
    print(f"  {len(vulns)} vulnérabilités trouvées")

    print(f"\n{Fore.CYAN}[3/5] Scan web...{Style.RESET_ALL}")
    if target.startswith("http"):
        web_target = target
    else:
        web_target = f"https://{target}"
    web_scanner = WebScanner(web_target)
    web_results = web_scanner.scan(depth=1)
    print(f"  {web_results['urls_found']} URLs, {len(web_results['vulnerabilities'])} vulnérabilités")

    print(f"\n{Fore.CYAN}[4/5] Vérification phishing...{Style.RESET_ALL}")
    phishing = PhishingDetector()
    ph_result = phishing.analyze_domain(web_target)
    print(f"  Risque phishing: {ph_result['risk_score']:.1%}")

    print(f"\n{Fore.CYAN}[5/5] Test de mot de passe...{Style.RESET_ALL}")
    pwd_analyzer = PasswordAnalyzer()
    sample = "TestPassword123!@#"
    pwd_result = pwd_analyzer.analyze(sample)
    print(f"  (Démonstration) Force: {pwd_result['strength']} ({pwd_result['score']}/100)")

    print("\n" + "=" * 60)
    success("Analyse complète terminée!")

    vuln_summary = vuln_scanner.generate_summary()
    print(f"\n{Fore.CYAN}Rapport final:{Style.RESET_ALL}")
    print(f"  Cible: {target}")
    print(f"  Ports ouverts: {len(ports)}")
    print(f"  Score de vulnérabilité: {vuln_summary['score']} ({vuln_summary['risk_level']})")
    print(f"  Risque phishing: {ph_result['risk_score']:.1%}")
    print(f"  Risque web: {web_scanner.generate_summary()['risk_level']}")


def main():
    parser = argparse.ArgumentParser(
        description="CyberAI - Framework IA de Cybersécurité tout-en-un",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  cyber-ai ids                           # Détection d'intrusion
  cyber-ai malware -f fichier.exe        # Analyser un fichier
  cyber-ai scan 192.168.1.1              # Scan de ports
  cyber-ai scan google.com --vuln        # Scan de vulnérabilités
  cyber-ai phishing -u https://example.com  # Détection phishing
  cyber-ai logs -f access.log            # Analyse de logs
  cyber-ai password --generate           # Générer mot de passe
  cyber-ai password -p "monPassword123"  # Analyser mot de passe
  cyber-ai web https://example.com       # Scan web
  cyber-ai all example.com               # Analyse complète
  cyber-ai router --discover             # Découvrir les routeurs
  cyber-ai router 192.168.1.1            # Scanner un routeur
  cyber-ai router 192.168.1.1 --exploit  # Exploiter un routeur TP-Link/ZTE
  cyber-ai router 192.168.1.1 --bruteforce --threads 50  # Brute-force
  cyber-ai router 192.168.1.1 --extract --output config.json  # Extraire config
        """
    )

    subparsers = parser.add_subparsers(dest="module", help="Module à exécuter")

    parser_ids = subparsers.add_parser("ids", help="Détection d'intrusion réseau")
    parser_ids.add_argument("--analyze", action="store_true", help="Analyser une connexion exemple")

    parser_malware = subparsers.add_parser("malware", help="Analyse de malwares")
    parser_malware.add_argument("-f", "--file", help="Fichier à analyser")
    parser_malware.add_argument("-s", "--string", help="Chaîne à classifier")

    parser_scan = subparsers.add_parser("scan", help="Scanner de ports et vulnérabilités")
    parser_scan.add_argument("target", nargs="?", help="Cible (IP ou domaine)")
    parser_scan.add_argument("--quick", action="store_true", help="Scan rapide (ports 1-1024)")
    parser_scan.add_argument("--full", action="store_true", help="Scan complet (ports 1-65535)")
    parser_scan.add_argument("--vuln", action="store_true", help="Scan de vulnérabilités")

    parser_phishing = subparsers.add_parser("phishing", help="Détection de phishing")
    parser_phishing.add_argument("-u", "--url", help="URL à analyser")

    parser_logs = subparsers.add_parser("logs", help="Analyse de logs")
    parser_logs.add_argument("-f", "--file", help="Fichier de log à analyser")

    parser_password = subparsers.add_parser("password", help="Analyse de mots de passe")
    parser_password.add_argument("-p", "--password", help="Mot de passe à analyser")
    parser_password.add_argument("--generate", action="store_true", help="Générer un mot de passe sécurisé")
    parser_password.add_argument("--length", type=int, default=20, help="Longueur du mot de passe (défaut: 20)")

    parser_web = subparsers.add_parser("web", help="Scanner web")
    parser_web.add_argument("url", nargs="?", help="URL à scanner")
    parser_web.add_argument("--depth", type=int, default=2, help="Profondeur de crawl (défaut: 2)")
    parser_web.add_argument("--sqli", action="store_true", help="Tester SQL Injection uniquement")
    parser_web.add_argument("--xss", action="store_true", help="Tester XSS uniquement")

    parser_router = subparsers.add_parser("router", help="Exploitation de routeurs (TP-Link/ZTE)")
    parser_router.add_argument("target", nargs="?", help="IP du routeur cible")
    parser_router.add_argument("--discover", action="store_true", help="Découvrir les routeurs sur le réseau")
    parser_router.add_argument("--subnet", default="192.168.1.0/24", help="Sous-réseau à scanner (défaut: 192.168.1.0/24)")
    parser_router.add_argument("-u", "--username", help="Nom d'utilisateur (défaut: admin)")
    parser_router.add_argument("-p", "--password", help="Mot de passe (défaut: admin)")
    parser_router.add_argument("--bruteforce", action="store_true", help="Lancer le brute-force d'identifiants")
    parser_router.add_argument("--wordlist", help="Wordlist pour le brute-force")
    parser_router.add_argument("--threads", type=int, default=20, help="Nombre de threads (défaut: 20)")
    parser_router.add_argument("--exploit", action="store_true", help="Tenter l'exploitation RCE")
    parser_router.add_argument("--cmd", default="id", help="Commande à exécuter (défaut: id)")
    parser_router.add_argument("--extract", action="store_true", help="Extraire la configuration")
    parser_router.add_argument("--output", help="Fichier de sortie pour la configuration")
    parser_router.add_argument("--list-exploits", action="store_true", help="Lister les exploits disponibles")

    parser_all = subparsers.add_parser("all", help="Analyse complète (tout-en-un)")
    parser_all.add_argument("target", nargs="?", help="Cible (IP ou domaine)")

    parser_gui = subparsers.add_parser("gui", help="Lancer l'interface graphique")

    parser_help = subparsers.add_parser("help", help="Aide détaillée")

    args = parser.parse_args()

    if args.module == "gui":
        from gui import main as gui_main
        gui_main()
        return

    if not args.module or args.module == "help":
        parser.print_help()
        print()
        print(banner())
        return

    modules = {
        "ids": cmd_intrusion,
        "malware": cmd_malware,
        "scan": cmd_scan,
        "phishing": cmd_phishing,
        "logs": cmd_logs,
        "password": cmd_password,
        "web": cmd_web,
        "router": cmd_router,
        "all": cmd_all,
    }

    if args.module in modules:
        modules[args.module](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
