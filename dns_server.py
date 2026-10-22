
import socket
import json
import sys
import time
import threading
from pathlib import Path

SERVERS = {
    "dns1": ("10.0.0.2", 15053),
    "dns2": ("10.0.0.3", 15054),
    "dns3": ("10.0.0.4", 15055)
}

RECORDS_FILE = Path(__file__).resolve().parent / "config" / "records.json"

TIMEOUT = 1.0
CACHE_TTL = 30
HEALTH_CHECK_INTERVAL = 2
MAX_HEALTH_FAILURES = 3

SDN_CONTROLLER_ADDRESS = ("10.0.0.254", 16000)
HEARTBEAT_INTERVAL = 2


def load_records(server_name):
    with open(RECORDS_FILE, "r") as file:
        all_records = json.load(file)

    return all_records[server_name]


def send_heartbeat(server_name):

    message = f"{server_name}|HEARTBEAT"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(
                message.encode(),
                SDN_CONTROLLER_ADDRESS
            )

    except OSError as error:
        print(
            f"SDN HEARTBEAT FAILED: {error}",
            flush=True
        )


def heartbeat_monitor(server_name):

    print(
        f"SDN heartbeat reporting enabled for {server_name}",
        flush=True
    )

    while True:
        send_heartbeat(server_name)
        time.sleep(HEARTBEAT_INTERVAL)


def check_server(peer_name, peer_address):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(TIMEOUT)

        try:
            sock.sendto(b"HEALTH_CHECK", peer_address)
            data, address = sock.recvfrom(1024)

            return (
                address == peer_address
                and data.decode() == "ALIVE"
            )

        except (socket.timeout, OSError):
            return False


def health_monitor(server_name, server_status, health_failures,
                   status_lock):

    while True:
        for peer_name, peer_address in SERVERS.items():

            if peer_name == server_name:
                continue

            is_alive = check_server(peer_name, peer_address)

            with status_lock:
                old_status = server_status[peer_name]

                if is_alive:
                    health_failures[peer_name] = 0
                    new_status = "ACTIVE"

                else:
                    health_failures[peer_name] += 1

                    if health_failures[peer_name] >= MAX_HEALTH_FAILURES:
                        new_status = "DOWN"
                    else:
                        new_status = old_status

                if new_status != old_status:

                    if new_status == "DOWN":
                        print(
                            f"SERVER STATUS: {peer_name} "
                            f"{old_status} -> DOWN "
                            f"(Health check failed: "
                            f"{MAX_HEALTH_FAILURES} consecutive timeouts)",
                            flush=True
                        )

                    else:
                        print(
                            f"SERVER STATUS: {peer_name} "
                            f"{old_status} -> ACTIVE "
                            f"(Health check successful)",
                            flush=True
                        )

                server_status[peer_name] = new_status

        time.sleep(HEALTH_CHECK_INTERVAL)


def forward_query(hostname, server_name, server_status, status_lock):

    for peer_name, peer_address in SERVERS.items():

        if peer_name == server_name:
            continue

        with status_lock:
            peer_status = server_status[peer_name]

        if peer_status == "DOWN":
            print(f"Skipping {peer_name}: server DOWN")
            continue

        print(f"Forwarding {hostname} to {peer_name}")

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(TIMEOUT)

            try:
                message = f"FORWARD|{hostname}"
                sock.sendto(message.encode(), peer_address)

                data, address = sock.recvfrom(1024)

                if address != peer_address:
                    print(f"Ignoring unexpected reply from {address}")
                    continue

                response = data.decode()

                if response.startswith("FOUND|"):
                    print(f"Resolved by {peer_name}")
                    return response

            except (socket.timeout, OSError):
                print(f"FORWARDING TIMEOUT: {peer_name}")
                print("Redirecting query to next server...")

    return "NOT_FOUND|Hostname not found"


def start_server(server_name):
    records = load_records(server_name)
    server_ip, port = SERVERS[server_name]

    cache = {}

    server_status = {
        name: "UNKNOWN"
        for name in SERVERS
        if name != server_name
    }

    health_failures = {
        name: 0
        for name in server_status
    }

    status_lock = threading.Lock()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:

        server.bind((server_ip, port))
        server.settimeout(1)

        print("====================================")
        print(f"       {server_name.upper()} SERVER")
        print("====================================")
        print(f"Listening on {server_ip}:{port}")
        print(f"Loaded {len(records)} records")
        print(f"Cache TTL: {CACHE_TTL} seconds")
        print(f"Health check interval: {HEALTH_CHECK_INTERVAL} seconds")
        print(f"Failure threshold: {MAX_HEALTH_FAILURES}")
        print(f"Heartbeat interval: {HEARTBEAT_INTERVAL} seconds")
        print("Health monitoring enabled")
        print("SDN heartbeat reporting enabled")
        print("Server ready...\n")

        monitor = threading.Thread(
            target=health_monitor,
            args=(
                server_name,
                server_status,
                health_failures,
                status_lock
            ),
            daemon=True
        )
        monitor.start()

        heartbeat_thread = threading.Thread(
            target=heartbeat_monitor,
            args=(server_name,),
            daemon=True
        )
        heartbeat_thread.start()

        while True:
            try:
                data, client_address = server.recvfrom(1024)

            except socket.timeout:
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
                    response = forward_query(
                        hostname,
                        server_name,
                        server_status,
                        status_lock
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
        print("Usage: python3 dns_server.py dns1|dns2|dns3")
        sys.exit(1)

    try:
        start_server(sys.argv[1])

    except KeyboardInterrupt:
        print("\nDNS server stopped")
