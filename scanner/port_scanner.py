import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from utils.helpers import info, success, warning, error


class PortScanner:
    def __init__(self, target=None, timeout=2.0, max_workers=100):
        self.target = target
        self.timeout = timeout
        self.max_workers = max_workers
        self.open_ports = []
        self.service_map = {
            20: "FTP-DATA", 21: "FTP", 22: "SSH", 23: "Telnet",
            25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
            135: "RPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS",
            445: "SMB", 465: "SMTPS", 514: "Syslog", 587: "SMTP",
            636: "LDAPS", 993: "IMAPS", 995: "POP3S", 1080: "SOCKS",
            1194: "OpenVPN", 1352: "Lotus Notes", 1433: "MSSQL",
            1521: "Oracle", 2049: "NFS", 2375: "Docker", 2376: "Docker TLS",
            3306: "MySQL", 3389: "RDP", 4333: "MariaDB", 5432: "PostgreSQL",
            5500: "VNC", 5900: "VNC", 5901: "VNC", 5984: "CouchDB",
            6379: "Redis", 6443: "HTTPS", 7070: "WebSphere",
            8000: "HTTP-Alt", 8080: "HTTP-Proxy", 8443: "HTTPS-Alt",
            9000: "PHP-FPM", 9090: "WebLogic", 9200: "Elasticsearch",
            11211: "Memcached", 27017: "MongoDB", 50070: "HDFS"
        }
        self.risk_ports = {
            21: "FTP - Trafic non chiffré",
            23: "Telnet - Trafic non chiffré",
            25: "SMTP - Spam potentiel",
            53: "DNS - Cache poisoning",
            135: "RPC - Vulnérabilités connues",
            139: "NetBIOS - Partage de fichiers",
            445: "SMB - EternalBlue/WannaCry",
            3389: "RDP - BlueKeep/RDP vulns",
            "all": "Port inhabituel"
        }

    def scan_port(self, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.target, port))
            if result == 0:
                service = self.service_map.get(port, "Inconnu")
                risk = "HAUT" if port in self.risk_ports else "MOYEN" if port < 1024 else "BAS"
                port_info = {
                    "port": port,
                    "state": "open",
                    "service": service,
                    "risk": risk,
                    "banner": self._grab_banner(port)
                }
                self.open_ports.append(port_info)
                warning(f"Port {port}/TCP ouvert - {service} [{risk}]")
            sock.close()
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        except Exception:
            pass

    def _grab_banner(self, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((self.target, port))
            banner = sock.recv(1024).decode("utf-8", errors="replace").strip()
            sock.close()
            return banner[:200] if banner else None
        except Exception:
            return None

    def scan(self, target=None, ports=None):
        if target:
            self.target = target
        if not self.target:
            error("Aucune cible spécifiée")
            return []

        info(f"Scan de {self.target}...")
        self.open_ports = []

        if ports is None:
            ports = self.service_map.keys()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self.scan_port, ports)

        self.open_ports.sort(key=lambda x: x["port"])
        success(
            f"Scan terminé: {len(self.open_ports)} port(s) ouvert(s) sur {self.target}"
        )
        return self.open_ports

    def quick_scan(self, target=None):
        return self.scan(target, range(1, 1025))

    def full_scan(self, target=None):
        return self.scan(target, range(1, 65536))

    def common_scan(self, target=None):
        return self.scan(target, self.service_map.keys())

    def get_summary(self):
        return {
            "target": self.target,
            "total_open": len(self.open_ports),
            "high_risk": len([p for p in self.open_ports if p["risk"] == "HAUT"]),
            "services": [p["service"] for p in self.open_ports if p["service"] != "Inconnu"]
        }
