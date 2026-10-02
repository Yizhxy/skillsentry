This network analysis task involves processing a packet capture file. All metrics must be computed from the raw pcap; do not rely on external data sources. Refer to the pcap-analysis skill guide for the recommended step-by-step procedure.

You have been provided with `packets.pcap` (subset of DAPT2020 traffic). Compute the stats and fill in only the `value` column in `/root/network_stats.csv`. Lines starting with `#` are comments—leave them.

Protocol counts
- `protocol_tcp`, `protocol_udp`, `protocol_icmp`, `protocol_arp`: packet counts by protocol
- `protocol_ip_total`: packets that contain an IP layer

Time / rate
- `duration_seconds`: last_timestamp − first_timestamp (seconds)
- `packets_per_minute_avg/max/min`: count packets per **120-second bucket**, then take avg/max/min

Sizes
- `total_bytes`: sum of packet lengths (bytes)
- `avg_packet_size`, `min_packet_size`, `max_packet_size`

Entropy (base 2 (Shannon))
Compute entropy over the observed frequency distribution:
- `src_ip_entropy`, `dst_ip_entropy`: entropy of src/dst IPs
- `src_port_entropy`, `dst_port_entropy`: entropy of src/dst ports
- `unique_src_ports`, `unique_dst_ports`: number of distinct src/dst ports

