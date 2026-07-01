You're given `packets.pcap` (subset of DAPT2020 traffic). Compute **all** the stats and fill in the `value` column in `/root/network_stats.csv`. Lines starting with `#` are comments—leave them.

**Additional (append to CSV):** `top_talker_ip` — the single source IP that sent the most packets.

You must compute all of the following categories (full pipeline required):

**Protocol counts:** `protocol_tcp`, `protocol_udp`, `protocol_icmp`, `protocol_arp`, `protocol_ip_total`

**Time / rate (60s buckets):** `duration_seconds`, `packets_per_minute_avg/max/min`

**Sizes:** `total_bytes`, `avg_packet_size`, `min_packet_size`, `max_packet_size`

**Entropy (Shannon, base 2):** `src_ip_entropy`, `dst_ip_entropy`, `src_port_entropy`, `dst_port_entropy`, `unique_src_ports`, `unique_dst_ports`

**Graph topology:** `num_nodes`, `num_edges`, `network_density`, `max_indegree`, `max_outdegree`

**Temporal patterns:** `iat_mean`, `iat_variance`, `iat_cv`, `num_producers`, `num_consumers`

**Flow metrics:** `unique_flows`, `bidirectional_flows`, `tcp_flows`, `udp_flows`

**Security patterns:** `is_traffic_benign`, `dominant_protocol`, `has_port_scan`, `has_dos_pattern`