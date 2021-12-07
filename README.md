# wrath

A highly performant networking tool optimized for scanning sizable port ranges as quickly as possible.

## How it works

For tackling this problem, `wrath` gathers all the ports together and slices the resulting set into optimally-sized batches. It then spawns several worker processes (proportionally to the count of CPU cores) and dispatches the slices. Consequently, this maximizes CPU utilization and uniformly distributes the load across the CPU cores. The worker processes are actors that communicate between themselves and the parent process via message passing.  Everything inside an actor happens asynchronously, unleashing the full power of parallelism united with asynchrony.

The scanning technique used is the so-called "stealth" (or "half-open") scanning, i.e., sending TCP packets with the SYN bit set and either waiting for SYN/ACK or RST/ACK. Upon receiving the response, the kernel sends back another TCP packet with the RST bit set, effectively closing the connection in the middle of the handshake. For receiving responses, `wrath` uses a raw AF_PACKET socket bound directly to the interface with a BPF filter applied.

## Results

In a lab environment with four cores and a direct 15m Category 6e link to the target router, `wrath` managed to inspect 64K ports in under 4 seconds.

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

## FAQ

**Q**: Was the pun in the name...?

**A**: Yes, the pun in the name was intended.

## Status

Usable, but still work in progress.
