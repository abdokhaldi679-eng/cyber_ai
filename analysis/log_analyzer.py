import re
from collections import defaultdict, Counter
from datetime import datetime
from utils.helpers import info, success, warning, error


class LogAnalyzer:
    def __init__(self):
        self.logs = []
        self.patterns = {
            "failed_login": re.compile(
                r"(?i)(failed|invalid|denied).*(login|password|auth)", re.IGNORECASE
            ),
            "sql_injection": re.compile(
                r"(?i)(union.*select|select.*from|drop\s+table|'
                 r"or\s+1=1|--\s|;|exec\s+xp_)",
                re.IGNORECASE
            ),
            "xss_attempt": re.compile(
                r"(?i)(<script|<iframe|javascript:|onerror=|onload=)",
                re.IGNORECASE
            ),
            "path_traversal": re.compile(
                r"(\.\./|\.\.\\|%2e%2e%2f|%252e%252e%252f|etc/passwd)",
                re.IGNORECASE
            ),
            "bruteforce": re.compile(
                r"(?i)(brute|hydra|medusa|nmap|masscan|zmap)", re.IGNORECASE
            ),
            "suspicious_ip": re.compile(
                r"\b(10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)\b"
            ),
        }

    def load_log(self, log_content):
        if isinstance(log_content, str):
            lines = log_content.split("\n")
        elif isinstance(log_content, list):
            lines = log_content
        else:
            error("Format de log non supporté")
            return

        for line in lines:
            if line.strip():
                self.logs.append({
                    "raw": line,
                    "timestamp": self._extract_timestamp(line),
                    "ip": self._extract_ip(line)
                })

        info(f"{len(lines)} lignes de log chargées")

    def analyze(self):
        if not self.logs:
            error("Aucun log à analyser")
            return {}

        results = {
            "total_lines": len(self.logs),
            "alerts": [],
            "ip_stats": defaultdict(int),
            "ip_threats": defaultdict(list),
            "timeline": defaultdict(int),
            "patterns_found": defaultdict(int),
            "attack_types": defaultdict(int)
        }

        for entry in self.logs:
            ip = entry["ip"]
            if ip:
                results["ip_stats"][ip] += 1

            for attack_type, pattern in self.patterns.items():
                if pattern.search(entry["raw"]):
                    results["patterns_found"][attack_type] += 1
                    if ip:
                        results["ip_threats"][ip].append(attack_type)

        results["failed_logins"] = results["patterns_found"]["failed_login"]
        results["sql_injections"] = results["patterns_found"]["sql_injection"]
        results["xss_attempts"] = results["patterns_found"]["xss_attempt"]

        for ip, threats in results["ip_threats"].items():
            if len(threats) >= 3:
                results["alerts"].append({
                    "type": "MULTIPLE_ATTACKS",
                    "ip": ip,
                    "threats": list(set(threats)),
                    "count": len(threats)
                })

        top_ips = sorted(
            results["ip_stats"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        results["top_ips"] = [
            {"ip": ip, "count": count} for ip, count in top_ips
        ]

        results["attack_summary"] = dict(
            sorted(results["patterns_found"].items(), key=lambda x: x[1], reverse=True)
        )

        return results

    def _extract_timestamp(self, line):
        patterns = [
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
            r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}",
            r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}",
        ]
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group()
        return None

    def _extract_ip(self, line):
        ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        match = re.search(ip_pattern, line)
        return match.group() if match else None

    def generate_report(self):
        results = self.analyze()
        if not results:
            return {}

        threat_score = (
            results["failed_logins"] * 2 +
            results["sql_injections"] * 5 +
            results["xss_attempts"] * 5 +
            len(results["alerts"]) * 10
        )

        return {
            "total_logs": results["total_lines"],
            "unique_ips": len(results["ip_stats"]),
            "alerts_count": len(results["alerts"]),
            "threat_score": threat_score,
            "risk_level": "CRITICAL" if threat_score > 100 else "HIGH" if threat_score > 50 else "MEDIUM" if threat_score > 10 else "LOW",
            "top_attackers": results["top_ips"][:5],
            "attack_types": results["attack_summary"]
        }
