

import subprocess

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


def create_topology():

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")
    h5 = net.addHost("h5", ip="10.0.0.5/24")

    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633
    )

    s1 = net.addSwitch(
        "s1",
        protocols="OpenFlow13",
        failMode="secure"
    )

    for host in [h1, h2, h3, h4, h5]:
        net.addLink(host, s1)

    net.start()

    # Controller communication interface
    subprocess.run(
        [
            "ovs-vsctl",
            "--may-exist",
            "add-port",
            "s1",
            "s1-ctrl",
            "--",
            "set",
            "Interface",
            "s1-ctrl",
            "type=internal"
        ],
        check=True
    )

    subprocess.run(
        [
            "ip",
            "addr",
            "replace",
            "10.0.0.254/24",
            "dev",
            "s1-ctrl"
        ],
        check=True
    )

    subprocess.run(
        [
            "ip",
            "link",
            "set",
            "s1-ctrl",
            "up"
        ],
        check=True
    )

    print("\nSDN controller communication interface ready")
    print("Interface: s1-ctrl")
    print("IP address: 10.0.0.254\n")

    CLI(net)

    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
