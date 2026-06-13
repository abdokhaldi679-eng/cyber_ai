import re
import requests
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from utils.helpers import info, success, warning, error


class WebScanner:
    def __init__(self, base_url=None):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CyberAI-Scanner/1.0 (Security Research)"
        })
        self.results = {
            "urls_found": [],
            "forms": [],
            "links": [],
            "vulnerabilities": [],
            "technologies": []
        }
        self.visited = set()

    def scan(self, url=None, depth=2):
        if url:
            self.base_url = url
        if not self.base_url:
            error("URL de base non spécifiée")
            return self.results

        info(f"Scan web de {self.base_url} (profondeur: {depth})...")
        self.results = {
            "urls_found": [],
            "forms": [],
            "links": [],
            "vulnerabilities": [],
            "technologies": []
        }
        self.visited = set()

        self._crawl(self.base_url, depth)
        self._check_technologies()
        self._test_common_vulnerabilities()

        success(f"Scan web terminé: {len(self.results['urls_found'])} URLs, "
                f"{len(self.results['forms'])} formulaires, "
                f"{len(self.results['vulnerabilities'])} vulnérabilités")

        return self.results

    def _crawl(self, url, depth):
        if depth <= 0 or url in self.visited:
            return

        self.visited.add(url)
        try:
            resp = self.session.get(url, timeout=10, verify=False)
            if resp.status_code != 200:
                return

            self.results["urls_found"].append(url)
            soup = BeautifulSoup(resp.text, "html.parser")

            for form in soup.find_all("form"):
                form_data = {
                    "url": url,
                    "action": form.get("action", ""),
                    "method": form.get("method", "GET").upper(),
                    "inputs": []
                }
                for inp in form.find_all("input"):
                    form_data["inputs"].append({
                        "name": inp.get("name", ""),
                        "type": inp.get("type", "text"),
                    })
                self.results["forms"].append(form_data)

                if form_data["method"] == "GET":
                    self.results["vulnerabilities"].append({
                        "type": "Formulaire GET",
                        "url": url,
                        "severity": "LOW",
                        "detail": "Formulaire en GET - les données sont visibles dans l'URL",
                        "remediation": "Utiliser la méthode POST"
                    })

            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(url, href)
                if self.base_url in full_url and full_url not in self.visited:
                    self._crawl(full_url, depth - 1)

        except requests.exceptions.SSLError:
            try:
                http_url = url.replace("https://", "http://")
                if http_url != url:
                    self._crawl(http_url, depth)
            except Exception:
                pass
        except Exception:
            pass

    def _check_technologies(self):
        try:
            resp = self.session.get(self.base_url, timeout=10, verify=False)
            headers = resp.headers

            techs = []
            if "X-Powered-By" in headers:
                techs.append(("Framework", headers["X-Powered-By"]))
            if "Server" in headers:
                techs.append(("Server", headers["Server"]))
            if "Set-Cookie" in str(headers):
                if "PHPSESSID" in str(headers):
                    techs.append(("PHP", "PHP"))
                if "JSESSIONID" in str(headers):
                    techs.append(("Java", "Java/ JSP"))
                if "ASP.NET" in str(headers) or "ASPSESSIONID" in str(headers):
                    techs.append(("ASP.NET", "ASP.NET"))

            if resp.text:
                if "wp-content" in resp.text:
                    techs.append(("CMS", "WordPress"))
                elif "Joomla" in resp.text:
                    techs.append(("CMS", "Joomla"))
                elif "Drupal" in resp.text:
                    techs.append(("CMS", "Drupal"))
                if "jquery" in resp.text.lower():
                    techs.append(("Library", "jQuery"))
                if "react" in resp.text.lower():
                    techs.append(("Framework", "React"))
                if "angular" in resp.text.lower():
                    techs.append(("Framework", "Angular"))
                if "vue" in resp.text.lower():
                    techs.append(("Framework", "Vue.js"))
                if "bootstrap" in resp.text.lower():
                    techs.append(("Framework", "Bootstrap"))

            self.results["technologies"] = techs
        except Exception:
            pass

    def _test_common_vulnerabilities(self):
        test_payloads = {
            "XSS": [
                "<script>alert(1)</script>",
                "<img src=x onerror=alert(1)>",
                "javascript:alert(document.cookie)",
            ],
            "SQLi": [
                "' OR '1'='1",
                "admin'--",
                "1; DROP TABLE users--",
                "1 UNION SELECT 1,2,3--",
            ],
            "LFI": [
                "../../etc/passwd",
                "..\\..\\windows\\win.ini",
                "%2e%2e%2f%2e%2e%2fetc/passwd",
            ]
        }

        for form in self.results["forms"]:
            action_url = urljoin(form["url"], form["action"]) if form["action"] else form["url"]

            for vuln_type, payloads in test_payloads.items():
                for payload in payloads:
                    try:
                        if form["method"] == "GET":
                            params = {}
                            for inp in form["inputs"]:
                                if inp["type"] not in ["submit", "hidden"]:
                                    params[inp["name"]] = payload
                            resp = self.session.get(
                                action_url, params=params, timeout=5, verify=False
                            )
                        else:
                            data = {}
                            for inp in form["inputs"]:
                                if inp["type"] not in ["submit"]:
                                    data[inp["name"]] = payload
                            resp = self.session.post(
                                action_url, data=data, timeout=5, verify=False
                            )

                        if vuln_type == "XSS" and payload in resp.text:
                            self.results["vulnerabilities"].append({
                                "type": "XSS (Cross-Site Scripting)",
                                "url": action_url,
                                "severity": "HIGH",
                                "payload": payload,
                                "detail": "Réflexion XSS détectée dans la réponse",
                                "remediation": "Échapper les entrées utilisateur"
                            })
                            break

                        if vuln_type == "SQLi":
                            for indicator in [
                                "sql", "mysql", "syntax error", "mysql_fetch",
                                "ODBC", "you have an error", "warning: mysql"
                            ]:
                                if indicator in resp.text.lower():
                                    self.results["vulnerabilities"].append({
                                        "type": "SQL Injection",
                                        "url": action_url,
                                        "severity": "CRITICAL",
                                        "payload": payload,
                                        "detail": f"Erreur SQL détectée: '{indicator}'",
                                        "remediation": "Utiliser des requêtes paramétrées"
                                    })
                                    break

                    except Exception:
                        pass

    def check_sql_injection(self, url):
        info(f"Test SQL Injection sur {url}...")
        payloads = [
            "'", "\"", "1=1", "1=2", "' OR '1'='1", "' OR 1=1--",
            "\" OR \"1\"=\"1", "admin'--", "1 UNION SELECT 1,2,3--",
            "' UNION SELECT @@version,2,3--", "1 AND 1=1", "1 AND 1=2"
        ]
        findings = []
        for payload in payloads:
            try:
                test_url = f"{url}?id={payload}"
                resp = self.session.get(test_url, timeout=5, verify=False)
                for indicator in [
                    "sql", "mysql", "syntax error", "mysql_fetch",
                    "ODBC", "you have an error", "warning: mysql"
                ]:
                    if indicator in resp.text.lower():
                        findings.append({
                            "payload": payload,
                            "indicator": indicator
                        })
                        break
            except Exception:
                pass

        if findings:
            warning(f"SQL Injection détectée sur {url}")
            self.results["vulnerabilities"].append({
                "type": "SQL Injection",
                "url": url,
                "severity": "CRITICAL",
                "findings": findings,
                "remediation": "Utiliser des requêtes paramétrées (Prepared Statements)"
            })
        return findings

    def check_xss(self, url):
        info(f"Test XSS sur {url}...")
        payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "\"><script>alert('XSS')</script>",
            "';alert('XSS');//"
        ]
        findings = []
        for payload in payloads:
            try:
                resp = self.session.get(
                    f"{url}?q={payload}", timeout=5, verify=False
                )
                if payload in resp.text:
                    findings.append(payload)
                    break
            except Exception:
                pass

        if findings:
            warning(f"XSS détectée sur {url}")
            self.results["vulnerabilities"].append({
                "type": "XSS (Cross-Site Scripting)",
                "url": url,
                "severity": "HIGH",
                "payloads": findings,
                "remediation": "Valider et échapper les entrées utilisateur"
            })
        return findings

    def get_report(self):
        vuln_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for v in self.results["vulnerabilities"]:
            sev = v.get("severity", "LOW")
            vuln_counts[sev] = vuln_counts.get(sev, 0) + 1

        return {
            "base_url": self.base_url,
            "total_urls": len(self.results["urls_found"]),
            "total_forms": len(self.results["forms"]),
            "total_vulnerabilities": len(self.results["vulnerabilities"]),
            "severity_counts": vuln_counts,
            "technologies": self.results["technologies"],
            "vulnerabilities": self.results["vulnerabilities"]
        }

    def generate_summary(self):
        report = self.get_report()
        score = (
            report["severity_counts"].get("CRITICAL", 0) * 10 +
            report["severity_counts"].get("HIGH", 0) * 5 +
            report["severity_counts"].get("MEDIUM", 0) * 2 +
            report["severity_counts"].get("LOW", 0) * 1
        )
        return {
            "target": report["base_url"],
            "score": score,
            "risk_level": "CRITICAL" if score >= 20 else "HIGH" if score >= 10 else "MEDIUM" if score >= 5 else "LOW",
            "vulnerabilities_found": report["total_vulnerabilities"],
            "urls_analyzed": report["total_urls"],
            "forms_analyzed": report["total_forms"],
            "technologies": [t[1] for t in report["technologies"]]
        }
