import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import tempfile
import json


class TestIntrusionDetector(unittest.TestCase):
    def setUp(self):
        from ids.intrusion_detector import IntrusionDetector
        self.detector = IntrusionDetector()

    def test_detect_connection(self):
        features = [10, 3, 500, 300, 0.5, 0.2, 5, 2, 0.8, 0.1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        result = self.detector.analyze_connection(features)
        self.assertIn("threat", result)
        self.assertIn("confidence", result)

    def test_predict(self):
        import numpy as np
        self.detector._load_or_create_default()
        X = np.random.randn(10, 21)
        preds = self.detector.predict(X)
        self.assertIsNotNone(preds)
        self.assertEqual(len(preds), 10)


class TestMalwareClassifier(unittest.TestCase):
    def setUp(self):
        from malware.classifier import MalwareClassifier
        self.classifier = MalwareClassifier()

    def test_analyze_strings_safe(self):
        result = self.classifier.analyze_strings("hello world test function")
        self.assertIn("is_malicious", result)
        self.assertIn("family", result)

    def test_analyze_strings_suspicious(self):
        result = self.classifier.analyze_strings(
            "encrypt file ransom bitcoin decrypt CreateRemoteThread inject"
        )
        self.assertIn("is_malicious", result)


class TestMalwareAnalyzer(unittest.TestCase):
    def setUp(self):
        from malware.analyzer import MalwareAnalyzer
        self.analyzer = MalwareAnalyzer()

    def test_analyze_binary(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as f:
            f.write(b"MZ" + b"\x00" * 100)
            f.write(b"CreateRemoteThread" + b"encrypt ransomware bitcoin")
            fname = f.name

        result = self.analyzer.analyze_file(fname)
        self.assertIsNotNone(result)
        self.assertIn("risk_score", result)
        self.assertIn("verdict", result)
        os.unlink(fname)


class TestPortScanner(unittest.TestCase):
    def setUp(self):
        from scanner.port_scanner import PortScanner
        self.scanner = PortScanner("127.0.0.1", timeout=0.5)

    def test_scan_localhost(self):
        results = self.scanner.quick_scan()
        self.assertIsInstance(results, list)


class TestPhishingDetector(unittest.TestCase):
    def setUp(self):
        from phishing.detector import PhishingDetector
        self.detector = PhishingDetector()

    def test_safe_url(self):
        result = self.detector.analyze_domain("https://www.google.com")
        self.assertFalse(result["is_phishing"])

    def test_phishing_url(self):
        result = self.detector.analyze_domain(
            "http://secure-login.xyz/verify/account"
        )
        self.assertTrue(result["is_phishing"])

    def test_extract_features(self):
        features = self.detector.extract_features("https://www.example.com/path")
        self.assertIn("url_length", features)
        self.assertIn("has_https", features)
        self.assertEqual(features["has_https"], 1)


class TestLogAnalyzer(unittest.TestCase):
    def setUp(self):
        from analysis.log_analyzer import LogAnalyzer
        self.analyzer = LogAnalyzer()

    def test_analyze_sample_logs(self):
        logs = """192.168.1.1 - - [01/Jan/2024:10:00:00] "POST /login HTTP/1.1" 401 128
192.168.1.2 - - [01/Jan/2024:10:01:00] "GET /products?id=1 UNION SELECT 1,2,3 HTTP/1.1" 200 500
203.0.113.5 - - [01/Jan/2024:10:02:00] "GET /search?q=<script>alert(1)</script> HTTP/1.1" 200 300"""
        self.analyzer.load_log(logs)
        report = self.analyzer.generate_report()
        self.assertIn("total_logs", report)
        self.assertIn("threat_score", report)
        self.assertGreater(report["total_logs"], 0)


class TestPasswordAnalyzer(unittest.TestCase):
    def setUp(self):
        from analysis.password_analyzer import PasswordAnalyzer
        self.analyzer = PasswordAnalyzer()

    def test_weak_password(self):
        result = self.analyzer.analyze("123456")
        self.assertLess(result["score"], 40)
        self.assertTrue(result["is_common"])

    def test_strong_password(self):
        result = self.analyzer.analyze("K#8mP2$vL9xQ!nR5")
        self.assertGreaterEqual(result["score"], 60)

    def test_generate_password(self):
        pwd = self.analyzer.generate_password(20)
        self.assertEqual(len(pwd), 20)
        result = self.analyzer.analyze(pwd)
        self.assertGreaterEqual(result["score"], 80)


class TestWebScanner(unittest.TestCase):
    def setUp(self):
        from web.web_scanner import WebScanner
        self.scanner = WebScanner()

    def test_extract_features(self):
        self.assertIsNotNone(self.scanner)


class TestRouterExploitDB(unittest.TestCase):
    def setUp(self):
        from router.exploit_db import ExploitDB
        self.db = ExploitDB()

    def test_summary(self):
        summary = self.db.get_summary()
        self.assertGreater(summary["total_exploits"], 0)
        self.assertIn("tplink", summary["brands"])
        self.assertIn("zte", summary["brands"])

    def test_search_tplink(self):
        results = self.db.search(brand="tplink")
        self.assertGreater(len(results), 0)
        self.assertTrue(all("tplink" in r["brand"].lower() for r in results))

    def test_search_zte(self):
        results = self.db.search(brand="zte")
        self.assertGreater(len(results), 0)
        self.assertTrue(all("zte" in r["brand"].lower() for r in results))

    def test_search_cve(self):
        results = self.db.search(cve="CVE-2021-27246")
        self.assertEqual(len(results), 1)


class TestRouterScanner(unittest.TestCase):
    def setUp(self):
        from router.scanner import RouterScanner
        self.scanner = RouterScanner()

    def test_scan_localhost(self):
        result = self.scanner.scan_single("127.0.0.1")
        self.assertIsNone(result)


class TestCredentialBruteforce(unittest.TestCase):
    def setUp(self):
        from router.credential_bruteforce import CredentialBruteforce
        self.bf = CredentialBruteforce()

    def test_generate_wordlist(self):
        words = self.bf.generate_wordlist(["admin"])
        self.assertGreater(len(words), 5)
        self.assertIn("admin", words)
        self.assertIn("admin123", words)


class TestConfigExtractor(unittest.TestCase):
    def setUp(self):
        from router.config_extractor import ConfigExtractor
        self.extractor = ConfigExtractor()

    def test_init(self):
        self.assertIsNotNone(self.extractor)


if __name__ == "__main__":
    unittest.main(verbosity=2)
