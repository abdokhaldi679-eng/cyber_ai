import requests
import socket
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.helpers import info, success, warning, error
from colorama import Fore, Style


class RouterScanner:
    def __init__(self):
        self.routers = []
        self.targets = []
        self.timeout = 3.0

    def discover(self, subnet="192.168.1.0/24", ports=[80, 443, 8080, 8443]):
        info(f"Découverte de routeurs sur {subnet}...")
        self.routers = []

        from ipaddress import ip_network
        network = ip_network(subnet, strict=False)
        ips = [str(ip) for ip in network.hosts()]

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {
                executor.submit(self._check_router, ip, ports): ip
                for ip in ips[:500]
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    self.routers.append(result)

        success(f"Découverte terminée: {len(self.routers)} routeur(s) trouvé(s)")
        return self.routers

    def scan_single(self, ip, ports=[80, 443, 8080, 8443]):
        result = self._check_router(ip, ports)
        if result:
            self.routers.append(result)
        return result

    def _check_router(self, ip, ports):
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                if sock.connect_ex((ip, port)) == 0:
                    sock.close()
                    return self._fingerprint(ip, port)
                sock.close()
            except Exception:
                pass
        return None

    def _fingerprint(self, ip, port):
        scheme = "https" if port in [443, 8443] else "http"
        info_router = {"ip": ip, "port": port, "scheme": scheme}

        try:
            resp = requests.get(
                f"{scheme}://{ip}:{port}/",
                timeout=self.timeout,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            headers = resp.headers
            server = headers.get("Server", "")
            www_auth = headers.get("WWW-Authenticate", "")
            realm = re.search(r'realm="([^"]+)"', www_auth)
            info_router["server"] = server
            info_router["realm"] = realm.group(1) if realm else ""
            info_router["status"] = resp.status_code

            body = resp.text

            if "TP-Link" in body or "TP-LINK" in body or "tp-link" in server.lower():
                info_router["brand"] = "TP-Link"
                info_router["model"] = self._extract_tplink_model(body, server)
                info_router["firmware"] = self._extract_firmware(body)

            elif "ZTE" in body or "zte" in server.lower() or "ZTE" in server:
                info_router["brand"] = "ZTE"
                info_router["model"] = self._extract_zte_model(body, server)
                info_router["firmware"] = self._extract_firmware(body)

            elif "router" in body.lower() or "gateway" in body.lower():
                info_router["brand"] = self._detect_brand(body, server)
                info_router["model"] = "Inconnu"

            else:
                info_router["brand"] = "Inconnu"
                info_router["model"] = "Inconnu"

            info_router["title"] = self._extract_title(body)
            self._check_open_ports(ip, info_router)

            warning(f"  Routeur détecté: {ip}:{port} - {info_router.get('brand', '?')} {info_router.get('model', '?')}")

        except requests.exceptions.SSLError:
            return self._fingerprint(ip, 80) if port != 80 else None
        except Exception:
            return None

        return info_router

    def _extract_tplink_model(self, body, server):
        patterns = [
            r'TP-LINK\s+(\S+?)<',
            r'modelName\s*=\s*["\']?([^"\'<]+)',
            r'TL-[WRAP][\w]+',
            r'Archer\s+\w+',
        ]
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(0)
        match = re.search(r'TL-\w+', server, re.IGNORECASE)
        return match.group(0) if match else "TP-Link (modèle inconnu)"

    def _extract_zte_model(self, body, server):
        patterns = [
            r'ZTE[-\s]*(\S+?)<',
            r'productName\s*=\s*["\']?([^"\'<]+)',
            r'ZXHN\s+\w+',
            r'MF\d{3}',
            r'F\d{3}[A-Z]?',
        ]
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(0)
        return "ZTE (modèle inconnu)"

    def _extract_firmware(self, body):
        patterns = [
            r'firmware[=:_]\s*["\']?([^"\'<&\s]+)',
            r'version[=:_]\s*["\']?([^"\'<&\s]+)',
            r'Firmware Version[=:_]\s*([^<]+)',
            r'Software Version[=:_]\s*([^<]+)',
            r'v(\d+\.\d+\.\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Inconnue"

    def _extract_title(self, body):
        match = re.search(r'<title>(.+?)</title>', body, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _detect_brand(self, body, server):
        brands = {
            "Huawei": ["huawei", "HG", "Huawei"],
            "MikroTik": ["mikrotik", "routeros", "MikroTik"],
            "Cisco": ["cisco", "Cisco"],
            "Netgear": ["netgear", "Netgear"],
            "D-Link": ["d-link", "DLINK", "D-Link"],
            "ASUS": ["asus", "ASUS"],
            "Linksys": ["linksys", "Linksys"],
            "Xiaomi": ["xiaomi", "Xiaomi", "Mi Router"],
        }
        for brand, keywords in brands.items():
            for kw in keywords:
                if kw.lower() in body.lower() or kw.lower() in server.lower():
                    return brand
        return "Générique"

    def _check_open_ports(self, ip, info_router):
        common_ports = [21, 22, 23, 53, 161, 443, 8080, 8443, 9999, 20000, 32764]
        open_ports = []
        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
                sock.close()
            except Exception:
                pass
        info_router["open_ports"] = open_ports

    def quick_scan(self, ip_range="192.168.1.0/24"):
        return self.discover(ip_range)
