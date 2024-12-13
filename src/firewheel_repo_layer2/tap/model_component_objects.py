# No need for secure random
from random import randint  # noqa: DUO102

from netaddr import EUI, mac_unix_expanded
from layer2.ovs import OpenvSwitch

from firewheel.control.experiment_graph import require_class


@require_class(OpenvSwitch)
class Tap:
    """Create a tap object.
    This is essentially an :py:class:`OpenvSwitch <layer2.ovs.OpenvSwitch>` object
    with additional functions to man-in-the-middle and/or mirror traffic.
    """

    def l2_mitm(self, bridge_name="br0"):
        """
        Create a layer 2 bridge that "breaks" the link, thus
        providing a position to mirror or man-in-the-middle traffic.

        Note:
            This function will pick up all interfaces on the VM
            that are not configured to have an IP address. The absence
            of layer 3 configuration is assumed to mean that the interface
            is only a layer 2 interface.

        Args:
            bridge_name (str): Name of the bridge to be created on the
                VM. All layer 2 interfaces then get dropped on the bridge
        """
        interfaces = []
        for interface in self.interfaces.interfaces:
            if "address" not in interface or not interface["address"]:
                if "mac" not in interface or not interface["mac"]:
                    # The top bit in MAC addresses is the multicast bit, therefore
                    # it must not be set. The second bit is the local bit. Easiest
                    # to just clear the top octet
                    # There are no security concerns with using random here.
                    mac = EUI(
                        randint(1000, 281474976710655) & 0x00FFFFFFFFFF,  # nosec B311
                        dialect=mac_unix_expanded,
                    )
                    interface["mac"] = str(mac)
                interfaces.append(interface["mac"].lower())

        self.bridge_layer2(-90, bridge_name=bridge_name, interfaces=interfaces)

    def mirror_traffic(self, bridge, *tunnel_params):
        """
        Once the layer 2 interfaces are all on the same bridge, mirror all
        traffic to the specified IP address. This is done by creating a GRE
        tunnel with the specified key. It is expected that the VM hosting the
        specified IP has a GRE endpoint configured.

        Args:
            bridge (str): Name of the bridge holding the interfaces that will
                have their traffic mirrored.
            *tunnel_params (tuple): Each parameter set is a tuple in the form of ``(ip, key)``
                where ``ip`` is the remote IP of the GRE tunnel and ``key`` is the GRE key, which
                is just an integer, but the key must be set in the same way on both the local
                and remote GRE endpoints. This key also helps us distinguish various port/mirror IDs.

        Raises:
            ValueError: If the tunnel parameters are not provided.
        """
        if not tunnel_params:
            raise ValueError("Tunnel parameters need to be provided to mirror traffic.")

        arguments = ""
        mirror_ids = []
        for ip, key in tunnel_params:
            mirror_id = f"@m{key}"
            mirror_ids.append(mirror_id)
            arguments += (
                f"add-port {bridge} "
                f"gre{key} -- "
                f"set interface gre{key} type=gre options:remote_ip={ip} options:key={key} -- "
                f"--id=@p{key} get port gre{key} -- "
                f"--id={mirror_id} create mirror name=mirror{key} select-all=true output-port=@p{key} -- "
            )

        # Add all mirror IDs to the bridge
        arguments += f"set bridge {bridge} mirrors={','.join(mirror_ids)}"
        self.run_executable(-75, "ovs-vsctl", arguments)
