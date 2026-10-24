
import argparse
import csv
import os
import socket
import statistics
import time
from datetime import datetime


SERVERS = {
    "dns1": ("10.0.0.2", 15053),
    "dns2": ("10.0.0.3", 15054),
    "dns3": ("10.0.0.4", 15055)
}

HOSTNAMES = {
    "pes.local": "10.0.0.10",
    "google.local": "10.0.0.20",
    "github.local": "10.0.0.40",
    "amazon.local": "10.0.0.50"
}

RESULTS_FILE = "tests/performance_results.csv"


def identify_client():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("10.0.0.2", 15053))
        ip_address = sock.getsockname()[0]

    if ip_address == "10.0.0.1":
        return "h1"

    if ip_address == "10.0.0.5":
        return "h5"

    return ip_address


def query_dns(server_name, hostname, timeout):

    server_ip, server_port = SERVERS[server_name]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    start = time.perf_counter()

    try:
        sock.sendto(
            hostname.encode(),
            (server_ip, server_port)
        )

        response, address = sock.recvfrom(1024)

        latency = (
            time.perf_counter() - start
        ) * 1000

        result = response.decode().strip()

        expected = "FOUND|" + HOSTNAMES[hostname]

        success = result == expected

        return success, latency, result

    except socket.timeout:
        return False, timeout * 1000, "TIMEOUT"

    except OSError as error:
        return False, 0, str(error)

    finally:
        sock.close()


def save_results(rows):

    os.makedirs("tests", exist_ok=True)

    file_exists = os.path.exists(RESULTS_FILE)

    with open(
        RESULTS_FILE,
        "a",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "scenario",
                "client",
                "server",
                "hostname",
                "query",
                "success",
                "latency_ms",
                "response"
            ]
        )

        if not file_exists:
            writer.writeheader()

        writer.writerows(rows)


def run_test(args):

    client = identify_client()

    print("\n================================")
    print(" DISTRIBUTED DNS PERFORMANCE TEST")
    print("================================")
    print("Scenario:", args.scenario)
    print("Client:", client)
    print("Server:", args.server)
    print("Hostname:", args.hostname)
    print("Queries:", args.count)
    print()

    rows = []
    successful_latencies = []

    for i in range(args.count):

        success, latency, response = query_dns(
            args.server,
            args.hostname,
            args.timeout
        )

        if success:
            successful_latencies.append(latency)

        status = "PASS" if success else "FAIL"

        print(
            f"{i + 1:02d}: {status} "
            f"{latency:.3f} ms {response}"
        )

        rows.append({
            "timestamp": datetime.now().isoformat(),
            "scenario": args.scenario,
            "client": client,
            "server": args.server,
            "hostname": args.hostname,
            "query": i + 1,
            "success": success,
            "latency_ms": round(latency, 3),
            "response": response
        })

        time.sleep(args.interval)

    success_count = len(successful_latencies)

    success_rate = (
        success_count / args.count
    ) * 100

    print("\n---------- SUMMARY ----------")

    print(
        f"Success rate: {success_count}/"
        f"{args.count} = {success_rate:.1f}%"
    )

    if successful_latencies:

        print(
            f"Average latency: "
            f"{statistics.mean(successful_latencies):.3f} ms"
        )

        print(
            f"Minimum latency: "
            f"{min(successful_latencies):.3f} ms"
        )

        print(
            f"Maximum latency: "
            f"{max(successful_latencies):.3f} ms"
        )

    else:
        print("No successful queries.")

    save_results(rows)

    print("\nResults saved to:", RESULTS_FILE)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scenario",
        choices=["normal", "failover", "baseline"],
        required=True
    )

    parser.add_argument(
        "--server",
        choices=list(SERVERS.keys()),
        default="dns2"
    )

    parser.add_argument(
        "--hostname",
        choices=list(HOSTNAMES.keys()),
        default="google.local"
    )

    parser.add_argument(
        "--count",
        type=int,
        default=10
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=0.2
    )

    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")

    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    if args.interval < 0:
        parser.error("--interval cannot be negative")

    run_test(args)
