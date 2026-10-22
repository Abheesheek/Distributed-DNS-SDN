
# Distributed DNS-Like Name Resolution System Using SDN

## 1. Project Overview

This project implements a distributed DNS-like name resolution system using Python, Mininet, Open vSwitch, and the OS-Ken SDN controller.

The system resolves hostnames into IP addresses using three DNS servers. It supports distributed record lookup, caching, server health monitoring, and automatic failover through Software-Defined Networking (SDN).

When a DNS server becomes unavailable, the SDN controller detects the failure and dynamically redirects client DNS traffic to an available backup server using OpenFlow rules.

## 2. Objectives

- Implement a distributed DNS-like resolution system.
- Distribute hostname records across multiple DNS servers.
- Support UDP-based DNS queries and inter-server forwarding.
- Improve lookup performance using TTL-based caching.
- Detect server failures using heartbeat monitoring.
- Implement automatic DNS failover using SDN.
- Restore normal forwarding when failed servers recover.
- Evaluate DNS resolution latency and fault tolerance.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python | DNS client, servers, and controller logic |
| Mininet | Virtual network emulation |
| Open vSwitch | OpenFlow-enabled network switch |
| OS-Ken | SDN controller framework |
| OpenFlow 1.3 | Programmable packet forwarding |
| UDP | DNS queries, health checks, and heartbeats |
| JSON | DNS record configuration |

## 4. Network Architecture

The Mininet topology consists of one client, three DNS servers, one Open vSwitch, and one remote SDN controller.

```text
                    OS-Ken Controller
                     10.0.0.254
                          |
                    OpenFlow 1.3
                          |
                    Open vSwitch
                          |
          +---------------+---------------+
          |               |               |
      h1 Client        h2 DNS1         h3 DNS2
      10.0.0.1         10.0.0.2        10.0.0.3
                          |
                       h4 DNS3
                      10.0.0.4
```

All four Mininet hosts connect directly to the same Open vSwitch.

The controller runs outside the Mininet host namespaces and communicates with the switch through OpenFlow.

The `s1-ctrl` internal interface provides IP connectivity for DNS server heartbeat messages.

### DNS Server Configuration

| Server | Host | IP Address | UDP Port |
|---|---|---|---|
| DNS1 | h2 | 10.0.0.2 | 15053 |
| DNS2 | h3 | 10.0.0.3 | 15054 |
| DNS3 | h4 | 10.0.0.4 | 15055 |

## 5. DNS Resolution

The client sends a hostname query to a selected DNS server.

The receiving server checks:

1. Its locally stored DNS records.
2. Its DNS cache.
3. Other available DNS servers, if the hostname is not found locally.

If a matching record is found, the server returns the corresponding IP address.

The system uses a custom UDP-based DNS-like protocol rather than the standard DNS wire format.

## 6. Distributed Records and Replication

DNS records are stored in:

`config/records.json`

The configuration contains records associated with each DNS server.

DNS2 and DNS3 also contain backup copies of DNS1's records, allowing the system to continue resolving the configured hostnames when DNS1 becomes unavailable.

This implementation uses static record replication. Changes to the JSON file are not automatically synchronized between running servers.

## 7. DNS Caching

Each DNS server maintains an in-memory cache for successful forwarded lookups.

Cache features:

- TTL: 30 seconds
- Cache hit and miss reporting
- Automatic expiration of cached records
- Reduced forwarding overhead for repeated queries

The cache is cleared when the DNS server process stops.

## 8. Health Monitoring

The system uses two monitoring mechanisms.

### Peer Health Monitoring

DNS servers periodically send UDP health-check messages to other DNS servers.

- Health-check interval: 2 seconds
- Timeout: 1 second
- Failure threshold: 3 consecutive unsuccessful checks

### SDN Heartbeat Monitoring

Each DNS server sends heartbeat messages to the SDN controller.

- Heartbeat interval: 2 seconds
- Controller heartbeat timeout: 7 seconds
- Controller heartbeat endpoint: 10.0.0.254:16000

The controller maintains server states such as ACTIVE, DOWN, and UNKNOWN.

## 9. SDN-Based Automatic Failover

When a DNS server fails:

1. The controller detects missing heartbeats.
2. The failed server is marked DOWN.
3. An available backup server is selected.
4. OpenFlow rules redirect the affected client's DNS requests.
5. Return-path rules rewrite DNS responses so the client can receive replies transparently.

The controller uses OpenFlow 1.3 to modify destination and source IP addresses, MAC addresses, and UDP ports.

When the failed DNS server recovers, the controller detects its heartbeat and removes the corresponding failover rules.

### OpenFlow Rule Priorities

| Priority | Function |
|---|---|
| 0 | Default controller forwarding |
| 1 | MAC-learning forwarding |
| 10 | DNS-specific forwarding |
| 50 | Client DNS query interception |
| 100 | Dynamic DNS failover |

## 10. Project Structure

```text
Distributed-DNS-SDN/
├── client.py
├── dns_server.py
├── controller.py
├── run_controller.py
├── topology.py
├── config/
│   └── records.json
├── requirements.txt
├── .gitignore
└── README.md
```

## 11. Installation

The project requires a Linux environment with Python 3, Mininet, Open vSwitch, and OS-Ken.

Install the required system packages according to your Ubuntu version and Mininet setup.

Create a Python virtual environment for OS-Ken:

```bash
python3 -m venv ~/sdn-env
source ~/sdn-env/bin/activate
pip install -r requirements.txt
```

OS-Ken must be compatible with the installed Python version.

## 12. Running the Project

Open two Ubuntu terminals.

### Terminal 1: Start the SDN Controller

```bash
cd ~/Distributed-DNS-SDN
source ~/sdn-env/bin/activate
python run_controller.py
```

### Terminal 2: Start Mininet

```bash
cd ~/Distributed-DNS-SDN
sudo python3 topology.py
```

The topology script automatically configures the `s1-ctrl` interface with IP address `10.0.0.254/24`.

### Start the DNS Servers

At the Mininet prompt:

```bash
h2 python3 -u dns_server.py dns1 > /tmp/dns1.log 2>&1 &
h3 python3 -u dns_server.py dns2 > /tmp/dns2.log 2>&1 &
h4 python3 -u dns_server.py dns3 > /tmp/dns3.log 2>&1 &
```

### Start the DNS Client

```bash
h1 python3 client.py
```

Choose a DNS server and enter a hostname such as:

```text
amazon.local
```

Expected resolved IP:

```text
10.0.0.50
```

## 13. Testing

### Normal DNS Resolution

Run the client against DNS1, DNS2, and DNS3.

All three servers successfully resolved `amazon.local` to `10.0.0.50` during testing.

### Failure Detection

Stop one DNS server and observe the controller marking it DOWN after its heartbeat timeout.

### Automatic Failover

Query the failed DNS server through the client.

The controller redirects the query to an active backup DNS server.

### Recovery

Restart the failed DNS server.

The controller marks it ACTIVE and removes the corresponding failover rules.

### OpenFlow Verification

Display switch flow entries:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

Display dynamic failover rules:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1 | grep 'priority=100'
```

## 14. Verified Performance Results

Normal resolution of `amazon.local` after restarting the network:

| DNS Server | Resolved IP | Lookup Latency |
|---|---|---|
| DNS1 | 10.0.0.50 | 36.065 ms |
| DNS2 | 10.0.0.50 | 21.540 ms |
| DNS3 | 10.0.0.50 | 16.454 ms |

These are individual measurements from the test environment, not averages from repeated benchmark runs.

The system was also tested for:

- DNS server failure detection
- Automatic SDN query redirection
- Recovery after server restart
- Simultaneous DNS1 and DNS2 failure
- Dynamic OpenFlow rule installation
- Automatic removal of failover rules after recovery

## 15. Limitations

- The topology currently uses one DNS client.
- DNS records are statically configured.
- Record replication is not automatically synchronized.
- Client sessions do not currently expire automatically.
- The implementation uses a custom DNS-like protocol rather than standard DNS packets.
- Performance measurements depend on the virtualized test environment.

## 16. Conclusion

This project demonstrates how Software-Defined Networking can improve the fault tolerance of a distributed DNS-like name resolution system.

By combining distributed DNS servers, caching, heartbeat-based monitoring, and programmable OpenFlow forwarding, the system can detect DNS server failures and redirect client traffic to available backup servers.

The implementation illustrates the practical application of SDN in network service availability, dynamic traffic management, and fault-tolerant distributed systems.
