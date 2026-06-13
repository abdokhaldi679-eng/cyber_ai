import socket
import hashlib
import re
from colorama import Fore, Style, init

init(autoreset=True)


def banner():
    b = f"""
{Fore.RED}  ██████╗██╗   ██╗██████╗ ███████╗██████╗ {Style.RESET_ALL}
{Fore.RED} ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗{Style.RESET_ALL}
{Fore.RED} ██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝{Style.RESET_ALL}
{Fore.RED} ██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗{Style.RESET_ALL}
{Fore.RED} ╚██████╗   ██║   ██████╔╝███████╗██║  ██║{Style.RESET_ALL}
{Fore.RED}  ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝{Style.RESET_ALL}
{Fore.CYAN}  AI-Powered Cybersecurity Framework v1.0{Style.RESET_ALL}
{Fore.YELLOW}  "AI-puissance : L'IA au service de la sécurité"{Style.RESET_ALL}
"""
    return b


def info(msg):
    print(f"{Fore.BLUE}[*] {msg}{Style.RESET_ALL}")


def success(msg):
    print(f"{Fore.GREEN}[+] {msg}{Style.RESET_ALL}")


def warning(msg):
    print(f"{Fore.YELLOW}[!] {msg}{Style.RESET_ALL}")


def error(msg):
    print(f"{Fore.RED}[-] {msg}{Style.RESET_ALL}")


def resolve_domain(domain):
    try:
        return socket.gethostbyname(domain)
    except socket.gaierror:
        return None


def hash_file(filepath):
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (FileNotFoundError, PermissionError):
        return None


def extract_urls(text):
    pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[-\w/%~?&#=]*'
    return re.findall(pattern, text)


def ip_to_int(ip):
    try:
        parts = [int(x) for x in ip.split(".")]
        return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
    except (ValueError, IndexError):
        return 0
