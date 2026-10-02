The following network analysis task calls for handling a packet capture file. All metrics must be derived from the raw pcap; do not depend on external data sources. Consult the pcap-analysis skill guide for the suggested step-by-step procedure.

You're given `packets.pcap` (subset of DAPT2020 traffic). Calculate **all** the stats and populate the `value` column in `/root/network_stats.csv`. Lines starting with `#` are comments—keep them untouched.

You must calculate all of the following categories (full pipeline required):

**Protocol counts:** `protocol_tcp`, `protocol_udp`, `protocol_icmp`, `protocol_arp`, `protocol_ip_total`

**Time / rate (60s buckets):** `duration_seconds`, `packets_per_minute_avg/max/min`

**Sizes:** `total_bytes`, `avg_packet_size`, `min_packet_size`, `max_packet_size`

**Entropy (Shannon, base 2):** `src_ip_entropy`, `dst_ip_entropy`, `src_port_entropy`, `dst_port_entropy`, `unique_src_ports`, `unique_dst_ports`

**Graph topology:** `num_nodes`, `num_edges`, `network_density`, `max_indegree`, `max_outdegree`

**Temporal patterns:** `iat_mean`, `iat_variance`, `iat_cv`, `num_producers`, `num_consumers`

**Flow metrics:** `unique_flows`, `bidirectional_flows`, `tcp_flows`, `udp_flows`

**Security patterns:** `is_traffic_benign`, `dominant_protocol`, `has_port_scan`, `has_dos_pattern`

**Additional (append to CSV):** `top_talker_ip` — the one source IP that transmitted the most packets.
