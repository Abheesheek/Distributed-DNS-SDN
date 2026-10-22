
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

    for h in [h1, h2, h3, h4]:
        net.addLink(h, s1)

    net.start()

    CLI(net)

    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
