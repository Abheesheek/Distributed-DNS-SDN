
import socket
import time

SERVERS = {
    "dns1": ("10.0.0.2", 15053),
    "dns2": ("10.0.0.3", 15054),
    "dns3": ("10.0.0.4", 15055)
}


def start_client():
    print("====================================")
    print("       DISTRIBUTED DNS CLIENT")
    print("====================================")

    server_name = input(
        "Choose DNS server (dns1/dns2/dns3): "
    ).strip().lower()

    if server_name not in SERVERS:
        print("Invalid DNS server")
        return

    server_address = SERVERS[server_name]

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(5)

        while True:
            hostname = input(
                "\nEnter hostname (or exit): "
            ).strip().lower()

            if hostname == "exit":
                break

            if not hostname:
                print("Please enter a hostname")
                continue

            start_time = time.perf_counter()

            try:
                client.sendto(
                    hostname.encode(),
                    server_address
                )

                data, address = client.recvfrom(1024)

                latency = (
                    time.perf_counter() - start_time
                ) * 1000

                response = data.decode()

                if response.startswith("FOUND|"):
                    ip = response.split("|", 1)[1]
                    print(f"Hostname: {hostname}")
                    print(f"Resolved IP: {ip}")

                else:
                    print("Hostname not found")

                print(f"Lookup latency: {latency:.3f} ms")

            except socket.timeout:
                print("ERROR: DNS query timed out")


if __name__ == "__main__":
    start_client()

