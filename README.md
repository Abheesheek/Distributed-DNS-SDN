
# Distributed DNS-Like Name Resolution System Using SDN

**Computer Networks — Jackfruit Mini Project**

A distributed DNS-like name resolution system implemented using Python, Mininet, Open vSwitch, OpenFlow 1.3, and the OS-Ken SDN controller.

The project demonstrates distributed hostname resolution, UDP socket communication, DNS caching, server health monitoring, dynamic SDN-based failover, and automatic recovery.

The final implementation supports **two independent DNS clients and three distributed DNS servers**, connected through an OpenFlow-enabled virtual network.

---

## 1. Project Overview

This project implements a distributed DNS-like name resolution system using Python, Mininet, Open vSwitch, and the OS-Ken SDN controller.

The system resolves hostnames into IP addresses using three DNS servers. It supports distributed record lookup, caching, server health monitoring, and automatic failover through Software-Defined Networking (SDN).

When a DNS server becomes unavailable, the SDN controller detects the failure and dynamically redirects client DNS traffic to an available backup server using OpenFlow rules.

The final version extends the original implementation by introducing a second DNS client, allowing independent client sessions and demonstrating failover for multiple clients.

The project also includes automated performance evaluation under normal operation, SDN failover, and a controlled no-failover baseline.

## 2. Objectives

- Implement a distributed DNS-like resolution system.
- Distribute hostname records across multiple DNS servers.
- Support UDP-based DNS queries and inter-server forwarding.
- Improve lookup performance using TTL-based caching.
- Detect server failures using heartbeat monitoring.
- Implement automatic DNS failover using SDN.
- Restore normal forwarding when failed servers recover.
- Support multiple independent DNS clients.
- Maintain separate SDN failover behavior for different client sessions.
- Evaluate DNS resolution latency, success rate, and fault tolerance.
- Compare SDN failover against a controlled no-failover condition.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python 3 | DNS client, server, and controller logic |
| Mininet | Virtual network emulation |
| Open vSwitch | OpenFlow-enabled network switch |
| OS-Ken | SDN controller framework |
| OpenFlow 1.3 | Programmable packet forwarding |
| UDP | DNS queries, health checks, and heartbeats |
| JSON | DNS record configuration |
| Python virtual environment | Dependency isolation |
| Ubuntu Linux | Development and execution environment |
| Git and GitHub | Version control and documentation |

The controller environment was configured using Python 3.12, while Mininet and the DNS application processes use the appropriate system Python environment.

## 4. Network Architecture

The final Mininet topology consists of:

- Two DNS clients
- Three distributed DNS servers
- One Open vSwitch
- One remote OS-Ken SDN controller

### Architecture Diagram

```text
                    +----------------------+
                    |   OS-Ken Controller  |
                    |   127.0.0.1:6633     |
                    +----------+-----------+
                               |
                          OpenFlow 1.3
                               |
                    +----------+-----------+
                    |    Open vSwitch      |
                    |         s1           |
                    +----------+-----------+
                               |
              +----------------+----------------+
              |                |                |
       +------+------+  +------+------+  +------+------+
       |             |  |             |  |             |
      h1            h2 h3            h4 h5
    Client 1       DNS1 DNS2         DNS3 Client 2

    10.0.0.1    10.0.0.2 10.0.0.3 10.0.0.4 10.0.0.5
```

All five Mininet hosts connect directly to the same Open vSwitch, `s1`.

The controller runs outside the Mininet host namespaces and communicates with the switch through OpenFlow.

The `s1-ctrl` internal interface provides IP connectivity for DNS server heartbeat messages.

### Host Configuration

| Host | Role | IP Address | UDP Port |
|---|---|---|---|
| h1 | DNS Client 1 | 10.0.0.1 | Dynamic source port |
| h2 | DNS1 | 10.0.0.2 | 15053 |
| h3 | DNS2 | 10.0.0.3 | 15054 |
| h4 | DNS3 | 10.0.0.4 | 15055 |
| h5 | DNS Client 2 | 10.0.0.5 | Dynamic source port |

### Controller Configuration

| Parameter | Value |
|---|---|
| Controller framework | OS-Ken |
| OpenFlow version | 1.3 |
| OpenFlow connection | 127.0.0.1:6633 |
| Heartbeat interface | s1-ctrl |
| Heartbeat IP address | 10.0.0.254/24 |
| Heartbeat UDP port | 16000 |
| Controller heartbeat timeout | 7 seconds |

The `s1-ctrl` interface is created by `topology.py`.

**Important:** The controller must be started after Mininet creates this interface.

## 5. DNS Resolution

The client sends a hostname query to a selected DNS server using UDP.

The receiving server checks:

1. Its locally stored DNS records.
2. Its DNS cache.
3. Other available DNS servers, if the hostname is not found locally.

If a matching record is found, the server returns the corresponding IP address.

The system uses a custom UDP-based DNS-like protocol rather than the standard DNS wire format.

### Example

```text
Choose DNS server (dns1/dns2/dns3): dns1

Enter hostname (or exit): pes.local

Hostname: pes.local
Resolved IP: 10.0.0.10
Lookup latency: 9.631 ms
```

### Application Protocol

A successful DNS response uses the format:

```text
FOUND|10.0.0.10
```

An unsuccessful lookup can return:

```text
NOT_FOUND|Hostname not found
```

The servers also exchange application-specific forwarding and health-check messages.

This project does not implement the full RFC-compliant DNS protocol or standard DNS packet format.

## 6. Distributed Records and Replication

DNS records are stored in:

```text
config/records.json
```

The configuration contains records associated with each DNS server.

Examples of configured hostnames include:

| Hostname | IP Address |
|---|---|
| pes.local | 10.0.0.10 |
| google.local | 10.0.0.20 |
| youtube.local | 10.0.0.30 |
| github.local | 10.0.0.40 |
| amazon.local | 10.0.0.50 |
| mrd.local | 10.0.0.60 |

DNS2 and DNS3 also contain backup copies of DNS1's records, allowing the system to continue resolving the configured hostnames when DNS1 becomes unavailable.

This implementation uses **static record replication**.

Changes to the JSON file are not automatically synchronized between running servers.

### Distributed Lookup

If a hostname is not present in a server's local records or valid cache, the server can forward the query to an available peer.

This allows records distributed across different DNS servers to be resolved without requiring every server to own every record.

## 7. DNS Caching

Each DNS server maintains an in-memory cache for successful forwarded lookups.

Cache features:

- TTL: 30 seconds
- Cache hit and miss reporting
- Automatic expiration of cached records
- Reduced forwarding overhead for repeated queries

The cache is cleared when the DNS server process stops.

### Caching Process

1. A DNS server receives a hostname query.
2. It checks its locally configured records.
3. If the record is not local, it checks the cache.
4. If a valid cached entry exists, the server returns the stored result.
5. Otherwise, the server forwards the query to an available peer.
6. Successful forwarded results can be cached temporarily.

Caching reduces repeated inter-server communication.

## 8. Health Monitoring

The system uses two monitoring mechanisms.

### 8.1 Peer Health Monitoring

DNS servers periodically send UDP health-check messages to other DNS servers.

Configuration:

| Parameter | Value |
|---|---|
| Health-check interval | 2 seconds |
| Timeout | 1 second |
| Failure threshold | 3 consecutive unsuccessful checks |

The health-check protocol uses messages such as:

```text
HEALTH_CHECK
ALIVE
```

These checks help DNS servers avoid forwarding queries to unavailable peers.

### 8.2 SDN Heartbeat Monitoring

Each DNS server sends heartbeat messages to the SDN controller.

Configuration:

| Parameter | Value |
|---|---|
| Heartbeat interval | 2 seconds |
| Controller heartbeat timeout | 7 seconds |
| Controller heartbeat endpoint | 10.0.0.254:16000 |

The controller maintains server states such as:

```text
ACTIVE
DOWN
UNKNOWN
```

When a server stops sending heartbeats, the controller marks it DOWN.

Example:

```text
SDN HEALTH UPDATE: dns2 ACTIVE -> DOWN
```

When heartbeat messages resume:

```text
SDN HEALTH UPDATE: dns2 DOWN -> ACTIVE
```

## 9. SDN-Based Automatic Failover

When a DNS server fails:

1. The controller detects missing heartbeats.
2. The failed server is marked DOWN.
3. An available backup server is selected.
4. OpenFlow rules redirect affected client DNS requests.
5. Return-path rules rewrite DNS responses so the client receives replies transparently.

The controller uses OpenFlow 1.3 to modify destination and source IP addresses, MAC addresses, and UDP ports.

### Example: DNS2 Failure

Suppose Client 2 (`h5`) sends a query to DNS2.

```text
Client: h5
Selected DNS server: dns2
Requested hostname: amazon.local

DNS2 status: DOWN
```

The controller detects the failure and redirects the request to an available backup server.

The client can still receive:

```text
Hostname: amazon.local
Resolved IP: 10.0.0.50
```

The client does not need to manually select a different DNS server.

### Transparent Packet Rewriting

For traffic originally addressed to DNS2, the controller can rewrite the destination IP address and UDP port to those of the selected backup server.

For example, when DNS1 is selected as the backup:

```text
Original destination:
10.0.0.3:15054

Redirected destination:
10.0.0.2:15053
```

The corresponding response is rewritten to preserve the original server identity from the client's perspective.

This provides transparent SDN-controlled failover.

### OpenFlow Rule Priorities

| Priority | Function |
|---|---|
| 0 | Default controller forwarding |
| 1 | MAC-learning forwarding |
| 10 | DNS-specific forwarding |
| 50 | Client DNS query interception |
| 100 | Dynamic DNS failover |

Higher-priority failover rules override ordinary forwarding when required.

### Automatic Recovery

When the failed DNS server recovers, the controller detects its heartbeat and removes the corresponding failover rules.

Example:

```text
SDN HEALTH UPDATE: dns2 DOWN -> ACTIVE
SDN FAILOVER REMOVED: dns2
```

Normal forwarding is restored without requiring the client application to restart.

## 10. Multiple-Client Support

The original implementation supported one client.

The final implementation adds a second client:

```text
h1 = 10.0.0.1
h5 = 10.0.0.5
```

Both clients use the same `client.py` application.

The controller supports independent client sessions by tracking:

```text
Client IP address
Client UDP source port
Originally selected DNS server
```

This allows different clients to issue DNS queries independently and supports separate failover rules for affected client sessions.

### Verified Multiple-Client Functionality

The following tests were completed:

- h1 resolved `pes.local` through DNS1.
- h5 resolved `google.local` through DNS2.
- Both clients performed DNS queries simultaneously.
- Both clients successfully queried different DNS servers.
- h5 resolved `amazon.local` while DNS2 was DOWN.
- OpenFlow priority-100 failover rules were verified for client IP `10.0.0.5`.

The controller successfully supported the additional client in the five-host Mininet topology.

## 11. Project Structure

```text
Distributed-DNS-SDN/
├── client.py
├── dns_server.py
├── controller.py
├── run_controller.py
├── topology.py
├── config/
│   └── records.json
├── tests/
│   ├── performance_test.py
│   └── performance_results.csv
├── requirements.txt
├── .gitignore
└── README.md
```

### File Descriptions

| File | Purpose |
|---|---|
| client.py | Interactive UDP DNS client |
| dns_server.py | Distributed DNS server implementation |
| controller.py | OS-Ken controller, heartbeat monitoring, and SDN failover |
| run_controller.py | Controller application launcher |
| topology.py | Five-host Mininet topology |
| config/records.json | Distributed DNS record configuration |
| tests/performance_test.py | Automated DNS performance benchmark |
| tests/performance_results.csv | Recorded benchmark observations |
| requirements.txt | Python dependencies |
| .gitignore | Excluded generated files |
| README.md | Project documentation |

## 12. Installation

The project requires a Linux environment with Python 3, Mininet, Open vSwitch, and OS-Ken.

Install the required system packages according to your Ubuntu version and Mininet setup.

### Controller Python Environment

The working controller setup uses Python 3.12.

The environment was configured using `uv`:

```bash
uv python install 3.12
uv venv --python 3.12 ~/sdn-env
source ~/sdn-env/bin/activate
pip install -r requirements.txt
```

OS-Ken must be compatible with the installed Python version.

The Python virtual environment isolates the controller dependencies from the system Python environment.

### Repository Setup

Clone the project repository:

```bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd Distributed-DNS-SDN
```

Replace the placeholder with the actual GitHub repository URL.

## 13. Running the Project

Open two Ubuntu terminals.

### Terminal 1: Start Mininet

```bash
cd ~/Distributed-DNS-SDN
sudo mn -c
sudo python3 topology.py
```

The topology script configures:

- Five Mininet hosts
- One Open vSwitch
- OpenFlow 1.3
- Remote controller connection
- `s1-ctrl` interface with IP address `10.0.0.254/24`

At the Mininet prompt, verify connectivity:

```bash
pingall
```

The completed topology was tested with:

```text
0% dropped
```

### Terminal 2: Start the SDN Controller

After Mininet creates the `s1-ctrl` interface:

```bash
cd ~/Distributed-DNS-SDN
source ~/sdn-env/bin/activate
python run_controller.py
```

**Important:** Start Mininet before the controller.

The controller heartbeat listener binds to `10.0.0.254`. If this interface does not exist when the controller starts, the heartbeat listener may fail to bind.

If necessary, restart the controller after Mininet is running.

### Start the DNS Servers

At the Mininet prompt:

```bash
h2 python3 -u dns_server.py dns1 > /tmp/dns1.log 2>&1 &
h3 python3 -u dns_server.py dns2 > /tmp/dns2.log 2>&1 &
h4 python3 -u dns_server.py dns3 > /tmp/dns3.log 2>&1 &
```

Wait for the controller to detect the DNS servers as ACTIVE.

### Start Client 1

```bash
h1 python3 client.py
```

### Start Client 2

```bash
h5 python3 client.py
```

To run both clients simultaneously, attach separate terminals to the existing Mininet host namespaces.

Do not start another instance of `topology.py` while the current Mininet topology is running.

### Example Query

```text
Choose DNS server (dns1/dns2/dns3): dns1

Enter hostname (or exit): amazon.local

Hostname: amazon.local
Resolved IP: 10.0.0.50
```

## 14. Functional Testing

### 14.1 Normal DNS Resolution

Run the client against DNS1, DNS2, and DNS3.

All three servers successfully resolved `amazon.local` to `10.0.0.50` during initial testing.

### 14.2 Multiple-Client Testing

Both h1 and h5 were tested with different hostname queries and DNS server selections.

The clients were also tested simultaneously.

### 14.3 Failure Detection

Stop one DNS server:

```bash
h3 pkill -f '^python3 -u dns_server.py dns2$'
```

Observe the controller marking DNS2 DOWN after its heartbeat timeout.

### 14.4 Automatic Failover

Query DNS2 through a client while DNS2 is DOWN.

The controller redirects the query to an available backup DNS server.

### 14.5 Recovery

Restart DNS2:

```bash
h3 python3 -u dns_server.py dns2 > /tmp/dns2.log 2>&1 &
```

The controller marks it ACTIVE and removes the corresponding failover rules.

### 14.6 OpenFlow Verification

Display switch flow entries:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

Display dynamic failover rules:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1 | grep 'priority=100'
```

### 14.7 DNS1 Failure and Replicated Records

DNS1 was stopped to verify that its replicated records remained accessible.

Client h1 selected DNS1 and queried:

```text
pes.local
mrd.local
```

Both queries succeeded while DNS1 was unavailable.

DNS1 was subsequently restarted and returned to ACTIVE status.

### 14.8 Earlier Robustness Testing

The original implementation was also tested for:

- DNS server failure detection
- Automatic SDN query redirection
- Recovery after server restart
- Simultaneous DNS1 and DNS2 failure
- Dynamic OpenFlow rule installation
- Automatic removal of failover rules after recovery

These tests were documented during the earlier single-client development stage.

The latest five-host implementation was separately verified for DNS1 failure, DNS2 failure, multiple-client functionality, and recovery.

## 15. Initial Functional Performance Measurements

During earlier testing, the system resolved `amazon.local` after restarting the network.

| DNS Server | Resolved IP | Lookup Latency |
|---|---|---|
| DNS1 | 10.0.0.50 | 36.065 ms |
| DNS2 | 10.0.0.50 | 21.540 ms |
| DNS3 | 10.0.0.50 | 16.454 ms |

These are individual measurements from the test environment, not averages from repeated benchmark runs.

They are preserved from the original project documentation.

## 16. Automated Performance Evaluation

The final project includes an automated performance-testing script:

```text
tests/performance_test.py
```

The script sends repeated UDP DNS queries and records individual results in:

```text
tests/performance_results.csv
```

The following metrics were evaluated:

- Total DNS queries
- Successful DNS queries
- Success rate
- Average lookup latency
- Minimum lookup latency
- Maximum lookup latency

### Test Configuration

| Parameter | Value |
|---|---|
| Clients | h1 and h5 |
| Selected DNS server | DNS2 |
| Requested hostname | google.local |
| Queries per client per scenario | 10 |
| Query timeout | 2 seconds |
| Query interval | 0.2 seconds |
| Scenarios | Normal, Failover, Baseline |

The experiment consisted of 60 queries across both clients and all three scenarios.

### Scenario 1: Normal Operation

All DNS servers were ACTIVE.

Commands:

```bash
h1 python3 tests/performance_test.py --scenario normal --count 10
h5 python3 tests/performance_test.py --scenario normal --count 10
```

### Scenario 2: SDN Failover

DNS2 was stopped.

The controller detected the failure and installed dynamic OpenFlow redirection rules.

Commands:

```bash
h3 pkill -f '^python3 -u dns_server.py dns2$'
```

After DNS2 was marked DOWN:

```bash
h1 python3 tests/performance_test.py --scenario failover --count 10
h5 python3 tests/performance_test.py --scenario failover --count 10
```

### Scenario 3: No-Failover Baseline

DNS2 remained DOWN.

A temporary priority-200 OpenFlow drop rule was installed to block traffic intended for DNS2, preventing successful redirection.

```bash
sh ovs-ofctl -O OpenFlow13 add-flow s1 "priority=200,udp,nw_dst=10.0.0.3,tp_dst=15054,actions=drop"
```

The baseline tests were then executed:

```bash
h1 python3 tests/performance_test.py --scenario baseline --count 10
h5 python3 tests/performance_test.py --scenario baseline --count 10
```

After testing, the temporary rule was removed:

```bash
sh ovs-ofctl -O OpenFlow13 --strict del-flows s1 "priority=200,udp,nw_dst=10.0.0.3,tp_dst=15054"
```

DNS2 was restarted afterward.

**Note:** The baseline represents a controlled no-failover condition. It is not a separately implemented traditional DNS system.

## 17. Automated Performance Results

### Success Rate Comparison

| Scenario | h1 Successful Queries | h5 Successful Queries | Combined Success Rate |
|---|---|---|---|
| Normal Operation | 10/10 | 10/10 | 100% |
| SDN Failover | 10/10 | 10/10 | 100% |
| No-Failover Baseline | 0/10 | 0/10 | 0% |

### Latency Comparison

All values are in milliseconds.

| Metric | h1 Normal | h1 Failover | h1 Baseline | h5 Normal | h5 Failover | h5 Baseline |
|---|---|---|---|---|---|---|
| Average | 5.759 | 7.067 | N/A | 6.627 | 8.012 | N/A |
| Minimum | 4.136 | 5.250 | N/A | 3.052 | 5.441 | N/A |
| Maximum | 8.783 | 8.313 | N/A | 11.871 | 12.564 | N/A |
| Success Rate | 100% | 100% | 0% | 100% | 100% | 0% |

Latency statistics are calculated using successful queries only.

### Performance Analysis

For Client h1:

```text
Normal average latency:   5.759 ms
Failover average latency: 7.067 ms
Latency increase:         Approximately 22.7%
```

For Client h5:

```text
Normal average latency:   6.627 ms
Failover average latency: 8.012 ms
Latency increase:         Approximately 20.9%
```

Although SDN failover increased average lookup latency, both clients maintained 100% successful resolution.

When failover was deliberately blocked, both clients experienced 0% query success.

### Interpretation

The results demonstrate that SDN-based redirection can preserve DNS service availability during a server failure.

The additional latency represents the overhead associated with redirection and forwarding through the available backup infrastructure.

The benchmark was conducted in a virtualized Mininet environment using 10 queries per client per scenario.

These measurements demonstrate the behavior of the tested prototype and are not production-network performance guarantees.

## 18. DNS1 Failure and Record Replication Results

DNS1 was stopped, and Client h1 continued to select DNS1.

The following results were observed:

| Hostname | Resolved IP | Lookup Latency | Result |
|---|---|---|---|
| pes.local | 10.0.0.10 | 9.631 ms | PASS |
| mrd.local | 10.0.0.60 | 2.527 ms | PASS |

Both records were resolved successfully while DNS1 was unavailable.

This confirms that the tested replicated records remained accessible through the backup DNS infrastructure during the DNS1 failure scenario.

After testing, DNS1 was restarted and returned to ACTIVE status.

## 19. Application Robustness and Fault Tolerance

The project includes several mechanisms for fault tolerance.

### Distributed DNS Servers

Multiple DNS servers allow the application to continue resolving hostnames when an individual server fails.

### Peer Health Monitoring

DNS servers avoid forwarding queries to peers that have been detected as unavailable.

### Controller Heartbeat Monitoring

The SDN controller independently monitors server availability through periodic heartbeats.

### Dynamic SDN Failover

OpenFlow rules redirect DNS traffic intended for failed servers.

### Transparent Response Rewriting

Return-path rules allow clients to receive responses consistent with the originally selected DNS server.

### Static Record Replication

Important DNS records are present on backup servers, improving availability when DNS1 fails.

### Automatic Recovery

When a failed server resumes sending heartbeats, the controller restores normal forwarding.

### Multiple-Client Support

The controller supports independent DNS sessions from both h1 and h5.

## 20. Troubleshooting

### Mininet Requires Root Privileges

Start the topology using:

```bash
sudo python3 topology.py
```

### Controller Heartbeat Listener Cannot Bind

If the controller cannot bind to `10.0.0.254`, verify that Mininet has already created the `s1-ctrl` interface.

Start Mininet before the controller.

### Verify DNS Server Processes

At the Mininet prompt:

```bash
h2 pgrep -af 'dns_server.py dns1'
h3 pgrep -af 'dns_server.py dns2'
h4 pgrep -af 'dns_server.py dns3'
```

### Inspect DNS Server Logs

```bash
h2 tail -n 30 /tmp/dns1.log
h3 tail -n 30 /tmp/dns2.log
h4 tail -n 30 /tmp/dns3.log
```

### Inspect OpenFlow Rules

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

To inspect dynamic failover rules:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1 | grep 'priority=100'
```

### Remove Temporary Baseline Rules

If the priority-200 baseline drop rule remains installed, remove it using:

```bash
sh ovs-ofctl -O OpenFlow13 --strict del-flows s1 "priority=200,udp,nw_dst=10.0.0.3,tp_dst=15054"
```

Verify removal:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1 | grep 'priority=200'
```

No output indicates that no priority-200 rules remain.

### Clean Up Mininet

After exiting Mininet:

```bash
sudo mn -c
```

## 21. Limitations

- The implementation uses a custom DNS-like protocol rather than standard DNS packets.
- DNS records are statically configured.
- Record replication is not automatically synchronized.
- The current topology contains two configured DNS clients.
- Client sessions do not currently expire automatically.
- The controller maintains session information in memory.
- The network uses one OpenFlow switch and one SDN controller.
- The heartbeat listener depends on the `s1-ctrl` interface created by Mininet.
- Performance measurements depend on the virtualized test environment.
- The no-failover baseline was created using a temporary OpenFlow drop rule rather than a separate traditional DNS implementation.

## 22. Future Enhancements

Possible future improvements include:

- Dynamic DNS record synchronization
- Additional DNS clients and servers
- Automatic expiration of inactive client sessions
- Persistent DNS record storage
- Multiple SDN controllers
- Larger and more complex Mininet topologies
- Advanced failover load balancing
- More extensive performance benchmarking
- Standard DNS protocol compatibility
- Improved monitoring and visualization

## 23. Conclusion

This project demonstrates how Software-Defined Networking can improve the fault tolerance of a distributed DNS-like name resolution system.

By combining distributed DNS servers, caching, heartbeat-based monitoring, and programmable OpenFlow forwarding, the system can detect DNS server failures and redirect client traffic to available backup servers.

The final implementation extends the original project by supporting two independent DNS clients and evaluating performance under normal operation, SDN failover, and a controlled no-failover baseline.

Automated testing demonstrated 100% successful DNS resolution for both clients during normal operation and SDN failover, compared with 0% success when failover was deliberately blocked.

Additional testing confirmed successful resolution of replicated records during DNS1 failure and automatic restoration of server status after recovery.

The implementation illustrates the practical application of SDN in network service availability, dynamic traffic management, and fault-tolerant distributed systems.
