import re
import math
import hashlib
import requests
from utils.helpers import info, success, warning, error


class PasswordAnalyzer:
    def __init__(self):
        self.common_passwords = set([
            "123456", "password", "12345678", "qwerty", "123456789",
            "12345", "1234", "111111", "1234567", "sunshine",
            "qwerty123", "iloveyou", "princess", "admin", "welcome",
            "666666", "abc123", "football", "123123", "monkey",
            "letmein", "dragon", "11111111", "baseball", "adobe123",
            "master", "michael", "shadow", "654321", "superman",
            "qazwsx", "maggie", "password1", "password123", "ashley",
            "bailey", "shadow", "123qwe", "passw0rd", "trustno1",
            "sunshine1", "1234567890", "0987654321", "qwertyuiop",
            "1q2w3e4r", "zaq12wsx", "!@#$%^&*", "000000", "pass",
            "pass123", "admin123", "root", "toor", "changeme",
        ])
        self.leaked = set()

    def analyze(self, password):
        results = {
            "password": "*" * len(password),
            "length": len(password),
            "entropy": self._calculate_entropy(password),
            "crack_time": self._estimate_crack_time(password),
            "patterns": self._detect_patterns(password),
            "score": 0,
            "strength": "",
            "feedback": [],
            "is_common": password.lower() in self.common_passwords,
            "is_leaked": False
        }

        score = 0

        if results["length"] >= 16:
            score += 40
        elif results["length"] >= 12:
            score += 30
        elif results["length"] >= 8:
            score += 15
        else:
            results["feedback"].append("Le mot de passe est trop court (min 8 caractères)")

        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password))

        char_types = sum([has_upper, has_lower, has_digit, has_special])
        score += char_types * 10

        if has_upper:
            results["patterns"].append("Lettres majuscules")
        else:
            results["feedback"].append("Ajoutez des lettres majuscules")

        if has_lower:
            results["patterns"].append("Lettres minuscules")
        if has_digit:
            results["patterns"].append("Chiffres")
        else:
            results["feedback"].append("Ajoutez des chiffres")

        if has_special:
            results["patterns"].append("Caractères spéciaux")
        else:
            results["feedback"].append("Ajoutez des caractères spéciaux")

        if results["is_common"]:
            score = max(0, score - 40)
            results["feedback"].append("Ce mot de passe est trop commun")

        if self._is_sequential(password):
            score = max(0, score - 20)
            results["feedback"].append("Évitez les suites de caractères séquentiels")

        if self._is_repeating(password):
            score = max(0, score - 15)
            results["feedback"].append("Évitez les répétitions de caractères")

        results["score"] = min(score, 100)

        if results["score"] >= 80:
            results["strength"] = "TRES FORT"
        elif results["score"] >= 60:
            results["strength"] = "FORT"
        elif results["score"] >= 40:
            results["strength"] = "MOYEN"
        elif results["score"] >= 20:
            results["strength"] = "FAIBLE"
        else:
            results["strength"] = "TRES FAIBLE"

        return results

    def check_breach(self, password):
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]

        try:
            resp = requests.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                timeout=5
            )
            if resp.status_code == 200:
                for line in resp.text.split("\n"):
                    if line.startswith(suffix):
                        count = int(line.split(":")[1].strip())
                        return {
                            "is_breached": True,
                            "breach_count": count,
                            "message": f"Mot de passe compromis {count} fois!"
                        }
            return {"is_breached": False, "breach_count": 0, "message": "Aucune fuite trouvée"}
        except Exception:
            return {"is_breached": False, "breach_count": 0, "message": "Vérification impossible (hors ligne)"}

    def _calculate_entropy(self, password):
        charset = 0
        if re.search(r"[a-z]", password):
            charset += 26
        if re.search(r"[A-Z]", password):
            charset += 26
        if re.search(r"\d", password):
            charset += 10
        if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
            charset += 32
        if charset == 0:
            return 0.0
        return round(len(password) * math.log2(charset), 2)

    def _estimate_crack_time(self, password):
        entropy = self._calculate_entropy(password)
        rate_online = 1000
        rate_offline = 1e10

        time_online = (2 ** entropy) / rate_online
        time_offline = (2 ** entropy) / rate_offline

        def format_time(seconds):
            if seconds < 1:
                return "instantané"
            elif seconds < 60:
                return f"{int(seconds)} secondes"
            elif seconds < 3600:
                return f"{int(seconds / 60)} minutes"
            elif seconds < 86400:
                return f"{int(seconds / 3600)} heures"
            elif seconds < 2592000:
                return f"{int(seconds / 86400)} jours"
            elif seconds < 31536000:
                return f"{int(seconds / 2592000)} mois"
            elif seconds < 3.1536e16:
                return f"{int(seconds / 31536000)} années"
            else:
                return "des siècles"

        return {
            "online": format_time(time_online),
            "offline": format_time(time_offline),
            "entropy": entropy
        }

    def _detect_patterns(self, password):
        patterns = []
        if re.match(r"\d{2,4}$", password):
            patterns.append("Termine par des chiffres")
        if re.match(r"^[A-Z]", password):
            patterns.append("Commence par une majuscule")
        if re.search(r"(.)\1{2,}", password):
            patterns.append("Caractères répétés")
        if re.search(r"abc|bcd|cde|def|efg|fgh|123|234|345|456|567|678|789|qwe|wer|ert|rty|tyu|yui|uio|iop|asd|sdf|dfg|fgh|ghj|hjk|jkl|zxc|xcv|cvb|vbn|bnm", password.lower()):
            patterns.append("Séquence de clavier")
        return patterns

    def _is_sequential(self, password):
        sequences = ["abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm"]
        for seq in sequences:
            for i in range(len(seq) - 2):
                if seq[i:i+3].lower() in password.lower():
                    return True
        return False

    def _is_repeating(self, password):
        return bool(re.search(r"(.)\1{2,}", password))

    def generate_password(self, length=20):
        import secrets
        import string

        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            pwd = "".join(secrets.choice(chars) for _ in range(length))
            if (any(c.islower() for c in pwd) and
                any(c.isupper() for c in pwd) and
                any(c.isdigit() for c in pwd) and
                any(c in "!@#$%^&*" for c in pwd)):
                return pwd
