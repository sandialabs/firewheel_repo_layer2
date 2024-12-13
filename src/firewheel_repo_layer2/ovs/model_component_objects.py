from linux.ubuntu1604 import Ubuntu1604Server

from firewheel.control.experiment_graph import require_class


@require_class(Ubuntu1604Server)
class OpenvSwitch:
    """
    This object installs Open vSwitch on an Ubuntu server endpoint.
    Open vSwitch is useful for many applications. Specific use cases
    include transparent firewalls and passive taps, among other possible
    applications.
    """

    def __init__(self):
        """
        Install openvswitch-switch and related debian packages.
        """
        self.install_debs(-100, "openvswitch-switch.tgz")

    def bridge_layer2(self, time, bridge_name="br0", interfaces=None):
        """
        Create layer 2 connections by putting all the specified interfaces
        on a newly created bridge with the specified name.

        Args:
            time (int): Schedule time to execute the bridging VM resource on the VM.
            bridge_name (str): Name of bridge to create on the VM.
            interfaces (list): List of MAC addresses corresponding to the interfaces
                to be added to the layer 2 bridge. Uses MAC addresses because
                interface names aren't guaranteed to be consistent.
        """
        if not interfaces:
            interfaces = []
        argument = bridge_name
        for interface in interfaces:
            argument += f" {interface.lower()}"

        self.run_executable(time, "bridge_layer2.sh", argument, vm_resource=True)
