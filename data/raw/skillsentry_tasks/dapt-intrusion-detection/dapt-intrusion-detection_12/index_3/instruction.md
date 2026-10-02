The following network analysis task requires processing a packet capture file. All metrics must be computed from the raw pcap; do not rely on external data sources. Refer to the pcap-analysis skill guide for the recommended step-by-step procedure.

You're given `packets.pcap` (subset of DAPT2020 traffic). Compute the stats and fill in only the `value` column in `/root/network_stats.csv`. Lines starting with `#` are comments—leave them.

Protocol counts: `protocol_tcp`, `protocol_udp`, `protocol_icmp`, `protocol_arp` are packet counts by protocol, and `protocol_ip_total` is the number of packets that contain an IP layer.

Time / rate: `duration_seconds` is last_timestamp − first_timestamp (seconds). For `packets_per_minute_avg/max/min`, count packets per **120-second bucket**, then take avg/max/min.

Sizes: report `total_bytes` (sum of packet lengths (bytes)) along with `avg_packet_size`, `min_packet_size`, and `max_packet_size`.

Entropy (base 2 (Shannon)): compute entropy over the observed frequency distribution, where `src_ip_entropy` and `dst_ip_entropy` are the entropy of src/dst IPs and `src_port_entropy` and `dst_port_entropy` are the entropy of src/dst ports. Finally, `unique_src_ports` and `unique_dst_ports` give the number of distinct src/dst ports.

