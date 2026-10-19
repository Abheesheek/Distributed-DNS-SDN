
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


def create_topology():

    # Create the Mininet network
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    print("*** Creating hosts")

    # Add client and DNS server hosts
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")

    print("*** Creating switch")

    # Create Open vSwitch
    s1 = net.addSwitch(
        "s1",
        failMode="standalone"
    )

    print("*** Creating links")

    # Connect every host to the switch
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)
    net.addLink(h4, s1)

    print("*** Starting network")

    net.start()

    print("*** Testing connectivity")

    # Test communication between all hosts
    net.pingAll()

    print("*** Opening Mininet CLI")

    # Open interactive Mininet terminal
    CLI(net)

    print("*** Stopping network")

    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
