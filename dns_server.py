
import socket
import json
import sys
import time
from pathlib import Path

SERVER_IP = "127.0.0.1"

SERVERS = {
    "dns1": 15053,
    "dns2": 15054,
    "dns3": 15055
}

RECORDS_FILE = Path(__file__).resolve().parent / "config" / "records.json"

TIMEOUT = 1.0
CACHE_TTL = 30
HEALTH_CHECK_INTERVAL = 5


def load_records(server_name):
    with open(RECORDS_FILE, "r") as file:
        all_records = json.load(file)

    return all_records[server_name]


def check_server(peer_name, peer_port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(TIMEOUT)

        try:
            sock.sendto(
                b"HEALTH_CHECK",
                (SERVER_IP, peer_port)
            )

            data, address = sock.recvfrom(1024)

            return data.decode() == "ALIVE"

        except (socket.timeout, OSError):
            return False


def update_server_health(server_name, server_status,
                         last_health_check):

    current_time = time.monotonic()

    for peer_name, peer_port in SERVERS.items():

        if peer_name == server_name:
            continue

        if (current_time - last_health_check[peer_name]
                < HEALTH_CHECK_INTERVAL):
            continue

        is_alive = check_server(peer_name, peer_port)

        new_status = "ACTIVE" if is_alive else "DOWN"
        old_status = server_status[peer_name]

        if new_status != old_status:
            print(
                f"SERVER STATUS: {peer_name} "
                f"{old_status} -> {new_status}"
            )

        server_status[peer_name] = new_status
        last_health_check[peer_name] = time.monotonic()


def forward_query(hostname, server_name, server_status):

    for peer_name, peer_port in SERVERS.items():

        if peer_name == server_name:
            continue

        if server_status[peer_name] == "DOWN":
            print(f"Skipping {peer_name}: server DOWN")
            continue

        print(f"Forwarding {hostname} to {peer_name}")

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(TIMEOUT)

            try:
                message = f"FORWARD|{hostname}"

                sock.sendto(
                    message.encode(),
                    (SERVER_IP, peer_port)
                )

                data, address = sock.recvfrom(1024)
                response = data.decode()

                if server_status[peer_name] == "DOWN":
                    print(f"SERVER RECOVERED: {peer_name}")

                server_status[peer_name] = "ACTIVE"

                if response.startswith("FOUND|"):
                    print(f"Resolved by {peer_name}")
                    return response

            except (socket.timeout, OSError):
                print(f"FAILURE DETECTED: {peer_name}")
                server_status[peer_name] = "DOWN"
                print("Redirecting query to next server...")

    return "NOT_FOUND|Hostname not found"


def start_server(server_name):
    records = load_records(server_name)
    port = SERVERS[server_name]

    cache = {}

    server_status = {
        name: "UNKNOWN"
        for name in SERVERS
        if name != server_name
    }

    last_health_check = {
        name: float("-inf")
        for name in server_status
    }

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:

        server.bind((SERVER_IP, port))
        server.settimeout(1)

        print("====================================")
        print(f"       {server_name.upper()} SERVER")
        print("====================================")
        print(f"Listening on {SERVER_IP}:{port}")
        print(f"Loaded {len(records)} records")
        print(f"Cache TTL: {CACHE_TTL} seconds")
        print("Health monitoring enabled")
        print("Server ready...\n")

        while True:
            try:
                data, client_address = server.recvfrom(1024)

            except socket.timeout:
                update_server_health(
                    server_name,
                    server_status,
                    last_health_check
                )
                continue

            message = data.decode().strip()

            if message == "HEALTH_CHECK":
                server.sendto(b"ALIVE", client_address)
                continue

            if message.startswith("FORWARD|"):
                hostname = message.split("|", 1)[1].lower()
                forwarded = True
            else:
                hostname = message.lower()
                forwarded = False

            print(f"\nQuery received: {hostname}")

            if hostname in records:
                response = f"FOUND|{records[hostname]}"
                print(f"Local record found: {records[hostname]}")

            elif hostname in cache:
                cached_ip, expiry = cache[hostname]

                if time.monotonic() < expiry:
                    response = f"FOUND|{cached_ip}"
                    print(f"CACHE HIT: {hostname} -> {cached_ip}")

                else:
                    del cache[hostname]
                    print(f"CACHE EXPIRED: {hostname}")
                    response = None

            else:
                response = None
                print(f"CACHE MISS: {hostname}")

            if response is None:

                if forwarded:
                    response = "NOT_FOUND|Hostname not found"
                    print("Forwarded query not found locally")

                else:
                    update_server_health(
                        server_name,
                        server_status,
                        last_health_check
                    )

                    response = forward_query(
                        hostname,
                        server_name,
                        server_status
                    )

                    if response.startswith("FOUND|"):
                        ip = response.split("|", 1)[1]

                        cache[hostname] = (
                            ip,
                            time.monotonic() + CACHE_TTL
                        )

                        print(f"CACHE UPDATED: {hostname} -> {ip}")

            server.sendto(response.encode(), client_address)
            print(f"Response sent: {response}")


if __name__ == "__main__":

    if len(sys.argv) != 2 or sys.argv[1] not in SERVERS:
        print("Usage: python dns_server.py dns1|dns2|dns3")
        sys.exit(1)

    try:
        start_server(sys.argv[1])

    except KeyboardInterrupt:
        print("\nDNS server stopped")
