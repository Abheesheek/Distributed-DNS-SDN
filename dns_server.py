
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


def load_records(server_name):
    with open(RECORDS_FILE, "r") as file:
        all_records = json.load(file)

    return all_records[server_name]


def forward_query(hostname, server_name):
    for peer_name, peer_port in SERVERS.items():

        if peer_name == server_name:
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

                if response.startswith("FOUND|"):
                    print(f"Resolved by {peer_name}")
                    return response

            except socket.timeout:
                print(f"{peer_name} timed out")

            except OSError as error:
                print(f"Error contacting {peer_name}: {error}")

    return "NOT_FOUND|Hostname not found"


def start_server(server_name):
    records = load_records(server_name)
    port = SERVERS[server_name]

    cache = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((SERVER_IP, port))

        print("====================================")
        print(f"       {server_name.upper()} SERVER")
        print("====================================")
        print(f"Listening on {SERVER_IP}:{port}")
        print(f"Loaded {len(records)} records")
        print(f"Cache TTL: {CACHE_TTL} seconds")
        print("Server ready...\n")

        while True:
            data, client_address = server.recvfrom(1024)
            message = data.decode().strip()

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
                    response = forward_query(hostname, server_name)

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
