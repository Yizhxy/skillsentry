"""Tests for DAPT intrusion detection - variant (bucket=120s, entropy_base=2, focus=all)."""
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

class TestDAPTVariant:
    def test_file_exists(self):
        assert RESULTS_FILE.exists(), f"Output file {RESULTS_FILE} not found"

    def test_expected_values(self):
        results = load_results()
        for metric, expected in EXPECTED_VALUES.items():
            assert metric in results, f"Missing metric: {metric}"
            val = results[metric]
            if isinstance(expected, (int, float)):
                try:
                    computed = float(val)
                    if metric in ("min_packet_size","max_packet_size","total_packets",
                                  "protocol_tcp","protocol_udp","protocol_icmp","protocol_arp",
                                  "protocol_ip_total","unique_dst_ports","unique_src_ports",
                                  "packets_per_minute_max","packets_per_minute_min",
                                  "num_nodes","num_edges","max_indegree","max_outdegree",
                                  "num_producers","num_consumers","unique_flows",
                                  "bidirectional_flows","tcp_flows","udp_flows"):
                        tol = max(1, abs(expected) * 0.01)
                    elif "entropy" in metric:
                        tol = ENTROPY_TOLERANCE
                    else:
                        tol = TOLERANCE
                    assert abs(computed - float(expected)) <= tol, \
                        f"{metric}: expected {expected}, got {computed}, tolerance={tol}"
                except ValueError:
                    pytest.fail(f"{metric}: expected numeric, got {val}")
            else:
                assert val.lower() == str(expected).lower(), f"{metric}: expected {expected}, got {val}"
