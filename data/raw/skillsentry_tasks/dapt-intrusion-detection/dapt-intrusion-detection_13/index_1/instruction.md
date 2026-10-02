The following network analysis task calls for handling a packet capture file. All metrics must be derived from the raw pcap; do not depend on external data sources. Consult the pcap-analysis skill guide for the suggested step-by-step procedure.

You're given `packets.pcap` (subset of DAPT2020 traffic). Calculate the stats and populate only the `value` column in `/root/network_stats.csv`. Lines starting with `#` are comments—keep them untouched.

Protocol counts
- `protocol_tcp`, `protocol_udp`, `protocol_icmp`, `protocol_arp`: packet counts by protocol
- `protocol_ip_total`: packets that include an IP layer

Time / rate
- `duration_seconds`: last_timestamp − first_timestamp (seconds)
- `packets_per_minute_avg/max/min`: count packets per **60-second bucket**, then obtain avg/max/min

Sizes
- `total_bytes`: sum of packet lengths (bytes)
- `avg_packet_size`, `min_packet_size`, `max_packet_size`

Entropy (base 10)
Calculate entropy over the observed frequency distribution:
- `src_ip_entropy`, `dst_ip_entropy`: entropy of src/dst IPs
- `src_port_entropy`, `dst_port_entropy`: entropy of src/dst ports
- `unique_src_ports`, `unique_dst_ports`: number of distinct src/dst ports

