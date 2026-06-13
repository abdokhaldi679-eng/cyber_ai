import threading
import time
from collections import defaultdict
from utils.helpers import info, warning, error


class NetworkMonitor:
    def __init__(self, interface=None):
        self.interface = interface
        self.packet_count = 0
        self.connections = defaultdict(list)
        self.alerts = []
        self.running = False
        self.thresholds = {
            "syn_flood": 100,
            "port_scan": 50,
            "ddos": 500,
            "icmp_flood": 50,
        }
        self._syn_count = defaultdict(int)
        self._port_scan_count = defaultdict(set)
        self._icmp_count = defaultdict(int)

    def start(self):
        self.running = True
        info("Network Monitor démarré (mode simulation)")
        info("Surveillance des anomalies réseau en temps réel...")
        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()

    def stop(self):
        self.running = False
        info("Network Monitor arrêté")

    def _monitor_loop(self):
        while self.running:
            self._check_thresholds()
            time.sleep(2)

    def analyze_packet(self, packet_info):
        self.packet_count += 1
        src_ip = packet_info.get("src_ip", "0.0.0.0")
        dst_ip = packet_info.get("dst_ip", "0.0.0.0")
        dst_port = packet_info.get("dst_port", 0)
        protocol = packet_info.get("protocol", "TCP")
        flags = packet_info.get("flags", "")

        connection_key = f"{src_ip}:{dst_ip}:{dst_port}"
        self.connections[connection_key].append(packet_info)

        if "SYN" in flags and "ACK" not in flags:
            self._syn_count[src_ip] += 1
            if self._syn_count[src_ip] > self.thresholds["syn_flood"]:
                self._trigger_alert("SYN_FLOOD", src_ip, dst_ip)

        if dst_port > 0:
            self._port_scan_count[src_ip].add(dst_port)
            if len(self._port_scan_count[src_ip]) > self.thresholds["port_scan"]:
                self._trigger_alert("PORT_SCAN", src_ip, dst_ip)

        if protocol == "ICMP":
            self._icmp_count[src_ip] += 1
            if self._icmp_count[src_ip] > self.thresholds["icmp_flood"]:
                self._trigger_alert("ICMP_FLOOD", src_ip, dst_ip)

        current_total = sum(len(v) for v in self.connections.values())
        if current_total > self.thresholds["ddos"]:
            self._trigger_alert("DDoS", "MULTIPLE_SOURCES", dst_ip)

    def _check_thresholds(self):
        now = time.time()
        for src, count in list(self._syn_count.items()):
            if count > self.thresholds["syn_flood"] * 5:
                self._trigger_alert("PERSISTENT_SYN_FLOOD", src, "GLOBAL")

    def _trigger_alert(self, alert_type, src, dst):
        alert = {
            "type": alert_type,
            "source": src,
            "destination": dst,
            "timestamp": time.time(),
            "severity": "HIGH" if alert_type in ["DDoS", "PERSISTENT_SYN_FLOOD"] else "MEDIUM"
        }
        self.alerts.append(alert)
        warning(f"ALERTE {alert['severity']}: {alert_type} de {src} vers {dst}")

    def get_stats(self):
        return {
            "packets_analyzed": self.packet_count,
            "active_connections": len(self.connections),
            "alerts_count": len(self.alerts),
            "recent_alerts": self.alerts[-10:] if self.alerts else []
        }

    def get_alerts(self, limit=50):
        return self.alerts[-limit:] if self.alerts else []
