# wrath

A highly performant networking tool optimized for scanning sizable port ranges as quickly as possible.

For tackling this problem, each range is sliced into optimally-sized batches. Then, a number of worker processes proportional to the number of CPU cores are spawned and batches are dispatched to them, thus providing for uniform distribution of the load across the cores. The worker processes are actually actors that communicate by passing messages to each other. Everything inside an actor happens asynchronously, allowing for the full power of asynchrony united with parallelism to be unleashed.

The scanning technique used is the so-called "stealth" (or "half-open") scanning, i.e., sending TCP packets with the SYN bit set and either waiting for SYN/ACK or RST/ACK. Upon receipt of a packet, the kernel sends back another packet with the RST bit set, effectively closing the connection in the middle of the handshake. For receiving responses, a raw AF_PACKET socket bound directly to the interface with a BPF filter applied is used.

In a lab environment with 4 cores and a direct Category 5e link to the target router, 64K ports were scanned in several seconds.

```sh
$ time sudo $pyexe -m wrath 192.168.1.1 -r 0-65535 -i enp5s0
53: open
80: open
515: open
18017: open
5473: open
3394: open
9100: open
47287: open
3838: open

real	0m3,985s
user	0m9,942s
sys	0m1,124s
```

Yes, the pun in the name was intended.

## Status

Work in progress.