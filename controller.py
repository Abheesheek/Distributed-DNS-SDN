
import socket
import threading
import time

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import (
    packet, ethernet, ipv4, udp, ether_types
)


class DNSLearningSwitch(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    DNS_SERVERS = {
        "dns1": {
            "ip": "10.0.0.2",
            "port": 15053,
            "mac": "00:00:00:00:00:02",
            "switch_port": 2
        },
        "dns2": {
            "ip": "10.0.0.3",
            "port": 15054,
            "mac": "00:00:00:00:00:03",
            "switch_port": 3
        },
        "dns3": {
            "ip": "10.0.0.4",
            "port": 15055,
            "mac": "00:00:00:00:00:04",
            "switch_port": 4
        }
    }

    CLIENTS = {
        "10.0.0.1": {
            "mac": "00:00:00:00:00:01",
            "switch_port": 1
        },
        "10.0.0.5": {
            "mac": "00:00:00:00:00:05",
            "switch_port": 5
        }
    }

    HEARTBEAT_TIMEOUT = 7
    FAILOVER_PRIORITY = 100

    def __init__(self, *args, **kwargs):
        super(DNSLearningSwitch, self).__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.datapaths = {}

        self.server_status = {
            name: "UNKNOWN"
            for name in self.DNS_SERVERS
        }

        self.last_heartbeat = {
            name: None
            for name in self.DNS_SERVERS
        }

        self.status_lock = threading.RLock()
        self.startup_time = time.monotonic()

        self.client_sessions = {}
        self.failover_rules = {}

        self.health_listener_thread = threading.Thread(
            target=self.health_listener,
            daemon=True
        )
        self.health_listener_thread.start()

        self.heartbeat_checker_thread = threading.Thread(
            target=self.check_heartbeat_timeouts,
            daemon=True
        )
        self.heartbeat_checker_thread.start()

    def update_server_status(self, server_name, new_status):

        old_status = self.server_status[server_name]

        if old_status == new_status:
            return

        self.server_status[server_name] = new_status

        print(
            f"SDN HEALTH UPDATE: {server_name} "
            f"{old_status} -> {new_status}",
            flush=True
        )

        self.update_failover_rules()

    def health_listener(self):

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:

                sock.bind(("10.0.0.254", 16000))

                print(
                    "DNS heartbeat listener started on "
                    "10.0.0.254:16000",
                    flush=True
                )

                while True:
                    data, address = sock.recvfrom(1024)

                    try:
                        message = data.decode().strip()
                        server_name, message_type = message.split("|", 1)

                    except (UnicodeDecodeError, ValueError):
                        continue

                    if server_name not in self.DNS_SERVERS:
                        continue

                    if address[0] != self.DNS_SERVERS[server_name]["ip"]:
                        continue

                    if message_type != "HEARTBEAT":
                        continue

                    with self.status_lock:

                        self.last_heartbeat[server_name] = (
                            time.monotonic()
                        )

                        self.update_server_status(
                            server_name, "ACTIVE"
                        )

        except OSError as error:
            print(
                f"DNS heartbeat listener error: {error}",
                flush=True
            )

    def check_heartbeat_timeouts(self):

        while True:
            time.sleep(1)
            current_time = time.monotonic()

            with self.status_lock:

                for server_name in self.DNS_SERVERS:

                    last_seen = self.last_heartbeat[server_name]

                    if last_seen is None:

                        if (
                            current_time - self.startup_time
                            > self.HEARTBEAT_TIMEOUT
                        ):
                            self.update_server_status(
                                server_name, "DOWN"
                            )

                        continue

                    if (
                        current_time - last_seen
                        > self.HEARTBEAT_TIMEOUT
                    ):
                        self.update_server_status(
                            server_name, "DOWN"
                        )

    def choose_backup(self, failed_server):

        for name in self.DNS_SERVERS:

            if (
                name != failed_server
                and self.server_status[name] == "ACTIVE"
            ):
                return name

        return None

    def add_flow(self, datapath, priority, match, actions):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow_mod)

    def delete_flow(self, datapath, match, priority):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE_STRICT,
            priority=priority,
            match=match,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )

        datapath.send_msg(flow_mod)

    def get_request_match(
        self, parser, client_ip, original_name, client_udp_port
    ):

        original = self.DNS_SERVERS[original_name]

        return parser.OFPMatch(
            in_port=self.CLIENTS[client_ip]["switch_port"],
            eth_type=0x0800,
            ip_proto=17,
            ipv4_src=client_ip,
            ipv4_dst=original["ip"],
            udp_src=client_udp_port,
            udp_dst=original["port"]
        )

    def get_reply_match(
        self, parser, client_ip, backup_name, client_udp_port
    ):

        backup = self.DNS_SERVERS[backup_name]

        return parser.OFPMatch(
            in_port=backup["switch_port"],
            eth_type=0x0800,
            ip_proto=17,
            ipv4_src=backup["ip"],
            ipv4_dst=client_ip,
            udp_src=backup["port"],
            udp_dst=client_udp_port
        )

    def get_failover_actions(
        self, parser, original_name, backup_name
    ):

        backup = self.DNS_SERVERS[backup_name]

        return [
            parser.OFPActionSetField(
                eth_dst=backup["mac"]
            ),
            parser.OFPActionSetField(
                ipv4_dst=backup["ip"]
            ),
            parser.OFPActionSetField(
                udp_dst=backup["port"]
            ),
            parser.OFPActionOutput(
                backup["switch_port"]
            )
        ]

    def install_failover(
        self, datapath, original_name,
        backup_name, client_ip, client_udp_port
    ):

        parser = datapath.ofproto_parser
        original = self.DNS_SERVERS[original_name]

        request_match = self.get_request_match(
            parser,
            client_ip,
            original_name,
            client_udp_port
        )

        request_actions = self.get_failover_actions(
            parser,
            original_name,
            backup_name
        )

        self.add_flow(
            datapath,
            self.FAILOVER_PRIORITY,
            request_match,
            request_actions
        )

        reply_match = self.get_reply_match(
            parser,
            client_ip,
            backup_name,
            client_udp_port
        )

        reply_actions = [
            parser.OFPActionSetField(
                eth_src=original["mac"]
            ),
            parser.OFPActionSetField(
                ipv4_src=original["ip"]
            ),
            parser.OFPActionSetField(
                udp_src=original["port"]
            ),
            parser.OFPActionOutput(
                self.CLIENTS[client_ip]["switch_port"]
            )
        ]

        self.add_flow(
            datapath,
            self.FAILOVER_PRIORITY,
            reply_match,
            reply_actions
        )

        print(
            f"SDN FAILOVER INSTALLED: "
            f"{original_name} -> {backup_name} "
            f"(client UDP {client_udp_port})",
            flush=True
        )

    def update_failover_rules(self):

        datapath = self.datapaths.get(1)

        if datapath is None:
            return

        parser = datapath.ofproto_parser

        for (client_ip, client_udp_port, original_name) in list(
            self.client_sessions
        ):

            session_key = (
                client_ip,
                client_udp_port,
                original_name
            )

            previous_backup = self.failover_rules.get(
                session_key
            )

            if self.server_status[original_name] == "DOWN":

                desired_backup = self.choose_backup(
                    original_name
                )

            else:
                desired_backup = None

            if previous_backup == desired_backup:
                continue

            if previous_backup is not None:

                request_match = self.get_request_match(
                    parser,
                    client_ip,
                    original_name,
                    client_udp_port
                )

                reply_match = self.get_reply_match(
                    parser,
                    client_ip,
                    previous_backup,
                    client_udp_port
                )

                self.delete_flow(
                    datapath,
                    request_match,
                    self.FAILOVER_PRIORITY
                )

                self.delete_flow(
                    datapath,
                    reply_match,
                    self.FAILOVER_PRIORITY
                )

                del self.failover_rules[session_key]

                print(
                    f"SDN FAILOVER REMOVED: "
                    f"{original_name}",
                    flush=True
                )

            if desired_backup is not None:

                self.install_failover(
                    datapath,
                    original_name,
                    desired_backup,
                    client_ip,
                    client_udp_port
                )

                self.failover_rules[
                    session_key
                ] = desired_backup

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        self.datapaths[datapath.id] = datapath

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            0,
            match,
            actions
        )

        # Intercept DNS queries from both clients.
        for client_ip, client in self.CLIENTS.items():

            for server_name, details in self.DNS_SERVERS.items():

                dns_match = parser.OFPMatch(
                    in_port=client["switch_port"],
                    eth_type=0x0800,
                    ip_proto=17,
                    ipv4_src=client_ip,
                    ipv4_dst=details["ip"],
                    udp_dst=details["port"]
                )

                self.add_flow(
                    datapath,
                    50,
                    dns_match,
                    actions
                )

        print(
            f"Switch connected: {datapath.id}",
            flush=True
        )

        with self.status_lock:
            self.update_failover_rules()

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if (
            eth is None
            or eth.ethertype == ether_types.ETH_TYPE_LLDP
        ):
            return

        src = eth.src
        dst = eth.dst
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        ip_packet = pkt.get_protocol(ipv4.ipv4)
        udp_packet = pkt.get_protocol(udp.udp)

        # Handle queries from either h1 or h5.
        if (
            ip_packet is not None
            and udp_packet is not None
            and ip_packet.src in self.CLIENTS
            and in_port == self.CLIENTS[ip_packet.src]["switch_port"]
        ):

            for name, details in self.DNS_SERVERS.items():

                if (
                    ip_packet.dst == details["ip"]
                    and udp_packet.dst_port == details["port"]
                ):

                    with self.status_lock:

                        client_udp_port = udp_packet.src_port
                        client_ip = ip_packet.src

                        session_key = (
                            client_ip,
                            client_udp_port,
                            name
                        )

                        self.client_sessions[
                            session_key
                        ] = time.monotonic()

                        self.update_failover_rules()

                        backup_name = self.failover_rules.get(
                            session_key
                        )

                        if backup_name is not None:

                            failover_actions = (
                                self.get_failover_actions(
                                    parser,
                                    name,
                                    backup_name
                                )
                            )

                            out = parser.OFPPacketOut(
                                datapath=datapath,
                                buffer_id=ofproto.OFP_NO_BUFFER,
                                in_port=in_port,
                                actions=failover_actions,
                                data=msg.data
                            )

                            datapath.send_msg(out)

                            print(
                                f"SDN QUERY REDIRECTED: "
                                f"{name} -> {backup_name}",
                                flush=True
                            )

                            return

                        if self.server_status[name] == "DOWN":

                            print(
                                f"SDN QUERY DROPPED: "
                                f"No active backup for {name}",
                                flush=True
                            )

                            return

                    break

        # Normal MAC-learning switch behavior.
        if dst in self.mac_to_port[dpid]:

            out_port = self.mac_to_port[dpid][dst]

        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        if out_port != ofproto.OFPP_FLOOD:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                1,
                match,
                actions
            )

            dns_ports = {
                details["mac"]: details["port"]
                for details in self.DNS_SERVERS.values()
            }

            if dst in dns_ports:

                dns_match = parser.OFPMatch(
                    in_port=in_port,
                    eth_type=0x0800,
                    ip_proto=17,
                    udp_dst=dns_ports[dst],
                    eth_dst=dst
                )

                self.add_flow(
                    datapath,
                    10,
                    dns_match,
                    actions
                )

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )

        datapath.send_msg(out)
