"""Tests for DAPT intrusion detection - full 9-step workflow."""
import csv
from pathlib import Path
import pytest

RESULTS_FILE = Path("/root/network_stats.csv")
TOLERANCE = 0.5
ENTROPY_TOLERANCE = 0.05

EXPECTED_VALUES = {
    "total_packets": 114099,
    "protocol_tcp": 32620,
    "protocol_udp": 26092,
    "protocol_icmp": 8,
    "protocol_arp": 54938,
    "protocol_ip_total": 58474,
    "duration_seconds": 26030.33,
    "packets_per_minute_avg": 262.9,
    "packets_per_minute_max": 4516,
    "packets_per_minute_min": 372,
    "total_bytes": 30889470,
    "avg_packet_size": 270.73,
    "min_packet_size": 42,
    "max_packet_size": 56538,
    "dst_port_entropy": 4.2811,
    "src_port_entropy": 4.3396,
    "src_ip_entropy": 2.4833,
    "dst_ip_entropy": 2.4618,
    "unique_dst_ports": 1675,
    "unique_src_ports": 1713,
    "num_nodes": 38,
    "num_edges": 58,
    "network_density": 0.041252,
    "max_indegree": 23,
    "max_outdegree": 27,
    "iat_mean": 0.22814,
    "iat_variance": 0.063282,
    "iat_cv": 1.1026,
    "num_producers": 23,
    "num_consumers": 13,
    "unique_flows": 3567,
    "bidirectional_flows": 1758,
    "tcp_flows": 3353,
    "udp_flows": 214,
    "is_traffic_benign": "true",
    "dominant_protocol": "arp",
    "has_port_scan": "false",
    "has_dos_pattern": "false",
}

def load_results():
    if not RESULTS_FILE.exists():
        return {}
    results = {}
    with open(RESULTS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = line.split(",")
            if len(parts) >= 2:
                results[parts[0].strip()] = parts[1].strip()
    return results

class TestDAPTFullWorkflow:
    def test_file_exists(self):
        assert RESULTS_FILE.exists()

    def test_all_required_metrics_present(self):
        results = load_results()
        for metric in EXPECTED_VALUES:
            assert metric in results, f"Missing required metric: {metric}"

    def test_expected_values(self):
        results = load_results()
        for metric, expected in EXPECTED_VALUES.items():
            assert metric in results, f"Missing: {metric}"
            val = results[metric]
            if isinstance(expected, (int, float)):
                computed = float(val)
                if metric in ("min_packet_size","max_packet_size","total_packets",
                              "protocol_tcp","protocol_udp","protocol_icmp","protocol_arp",
                              "protocol_ip_total","unique_dst_ports","unique_src_ports",
                              "packets_per_minute_max","packets_per_minute_min",
                              "num_nodes","num_edges","max_indegree","max_outdegree",
                              "num_producers","num_consumers","unique_flows",
                              "bidirectional_flows","tcp_flows","udp_flows","total_bytes"):
                    tol = max(1, abs(float(expected)) * 0.02)
                elif "entropy" in metric:
                    tol = ENTROPY_TOLERANCE
                else:
                    tol = TOLERANCE
                assert abs(computed - float(expected)) <= tol, \
                    f"{metric}: expected {expected}, got {computed}"
            else:
                assert val.lower() == str(expected).lower(), \
                    f"{metric}: expected {expected}, got {val}"

