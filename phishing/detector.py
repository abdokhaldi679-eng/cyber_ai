import re
import requests
import urllib.parse
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from utils.helpers import info, success, error


class PhishingDetector:
    def __init__(self, model_path=None):
        self.model = None
        self.model_path = model_path

    def extract_features(self, url):
        features = {}
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        features["url_length"] = len(url)
        features["domain_length"] = len(domain)
        features["num_dots"] = domain.count(".")
        features["num_hyphens"] = domain.count("-")
        features["num_underscores"] = domain.count("_")
        features["num_slashes"] = path.count("/")
        features["num_params"] = len(parsed.query.split("&")) if parsed.query else 0
        features["has_ip"] = 1 if re.match(r"\d+\.\d+\.\d+\.\d+", domain) else 0
        features["has_at_symbol"] = 1 if "@" in url else 0
        features["has_double_slash_redirect"] = 1 if "//" in url[8:] else 0
        features["has_https"] = 1 if parsed.scheme == "https" else 0
        features["num_subdomains"] = len(domain.split(".")) - 2
        features["has_port"] = 1 if parsed.port else 0

        suspicious_tlds = [
            ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top",
            ".work", ".date", ".men", ".loan", ".click", ".download",
            ".review", ".stream", ".bid", ".trade", ".webcam"
        ]
        features["suspicious_tld"] = 1 if any(
            domain.endswith(tld) for tld in suspicious_tlds
        ) else 0

        suspicious_keywords = [
            "login", "signin", "verify", "account", "update",
            "confirm", "secure", "bank", "paypal", "password",
            "credential", "authenticate", "reset", "validate",
            "security", "ebayisapi", "webscr", "cmd", "action",
            "auth", "token", "session", "redirect", "access"
        ]
        features["suspicious_keywords"] = sum(
            1 for kw in suspicious_keywords if kw in url.lower()
        )

        features["num_digits"] = sum(1 for c in domain if c.isdigit())
        features["ratio_digits"] = features["num_digits"] / max(len(domain), 1)

        return features

    def features_to_list(self, features):
        return [
            features["url_length"],
            features["domain_length"],
            features["num_dots"],
            features["num_hyphens"],
            features["num_slashes"],
            features["num_params"],
            features["has_ip"],
            features["has_at_symbol"],
            features["has_double_slash_redirect"],
            features["has_https"],
            features["num_subdomains"],
            features["has_port"],
            features["suspicious_tld"],
            features["suspicious_keywords"],
            features["ratio_digits"],
        ]

    def train(self, urls, labels):
        info("Entraînement du détecteur de phishing...")
        X = []
        for url in urls:
            features = self.extract_features(url)
            X.append(self.features_to_list(features))

        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=15, random_state=42, n_jobs=-1
        )
        self.model.fit(X, labels)

        benign_count = labels.count(0)
        phishing_count = labels.count(1)
        success(
            f"Détecteur entraîné: {benign_count} bénins, {phishing_count} phishing"
        )

    def predict(self, url):
        if self.model is None:
            self._load_or_create_default()

        features = self.extract_features(url)
        X = [self.features_to_list(features)]
        pred = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]

        return {
            "url": url,
            "is_phishing": bool(pred == 1),
            "confidence": float(max(proba)),
            "risk_score": float(proba[1]),
            "features": features
        }

    def analyze_domain(self, url):
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc

        result = self.predict(url)

        if result["is_phishing"]:
            reasons = self._get_phishing_reasons(result["features"])
        else:
            reasons = []

        result["domain"] = domain
        result["risk_factors"] = reasons
        return result

    def _get_phishing_reasons(self, features):
        reasons = []
        if features["has_ip"]:
            reasons.append("Utilise une adresse IP au lieu d'un nom de domaine")
        if features["has_at_symbol"]:
            reasons.append("Contient le symbole '@' pour masquer l'URL réelle")
        if features["suspicious_tld"]:
            reasons.append("Utilise un TLD suspect/ gratuit")
        if features["num_hyphens"] > 3:
            reasons.append("Nombre excessif de tirets dans le domaine")
        if features["suspicious_keywords"] > 2:
            reasons.append("Contient des mots-clés suspects")
        if not features["has_https"]:
            reasons.append("Site non chiffré (pas de HTTPS)")
        if features["ratio_digits"] > 0.5:
            reasons.append("Trop de chiffres dans le domaine")
        if features["url_length"] > 100:
            reasons.append("URL anormalement longue")
        return reasons

    def _load_or_create_default(self):
        model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        os.makedirs(model_dir, exist_ok=True)
        model_file = os.path.join(model_dir, "phishing_model.joblib")
        if os.path.exists(model_file):
            self.load(model_file)
            info("Modèle phishing chargé depuis le disque")
        else:
            self._create_default_model(model_file)

    def _create_default_model(self, model_file):
        info("Création d'un modèle phishing par défaut...")
        benign_urls = [
            "https://www.google.com/search",
            "https://github.com/login",
            "https://www.linkedin.com/in/user",
            "https://mail.google.com/mail",
            "https://www.amazon.com/products",
            "https://stackoverflow.com/questions",
            "https://www.python.org/downloads",
            "https://www.microsoft.com/software-download",
            "https://www.wikipedia.org/wiki/Main_Page",
            "https://twitter.com/home",
            "https://www.youtube.com/watch",
            "https://www.reddit.com/r/programming",
            "https://www.dropbox.com/login",
            "https://www.spotify.com/account",
            "https://www.netflix.com/browse",
        ] * 10
        phishing_urls = [
            "http://192.168.1.1/login.php?redirect=bank",
            "https://secure-login.xyz/verify/account",
            "http://paypa1.com.security-update.tk/",
            "https://login-bank-account.ml/verify",
            "http://www.amazon-login.ga/update-payment",
            "https://account-verify-123.xyz/login",
            "http://free-prize-winner.tk/claim-now",
            "https://www.paypal-security.com.work/",
            "http://bank-of-america.secure-login.ml",
            "https://reset-password-2024.ga/confirm",
            "http://dropbox-shared-file.xyz/download",
            "https://apple-id-verify.tk/account-locked",
            "http://netflix-renewal.ga/credit-card",
            "https://instagram-followers-free.tk/login",
            "http://windows-defender-alert.ml/scan",
        ] * 10
        urls = benign_urls + phishing_urls
        labels = [0] * len(benign_urls) + [1] * len(phishing_urls)
        self.train(urls, labels)
        self.save(model_file)

    def save(self, path):
        joblib.dump(self.model, path)
        success(f"Modèle phishing sauvegardé: {path}")

    def load(self, path):
        self.model = joblib.load(path)
        success(f"Modèle phishing chargé: {path}")
