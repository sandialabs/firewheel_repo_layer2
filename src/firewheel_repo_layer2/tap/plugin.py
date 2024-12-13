from netaddr import IPNetwork
from layer2.tap import Tap
from base_objects import Switch, FalseEdge, VMEndpoint

from firewheel.control.experiment_graph import Vertex, AbstractPlugin


class InsertTaps(AbstractPlugin):
    """
    This plugin inserts a passive tap on designated edges and tunnels
    all mirrored traffic to the "collector" (i.e. Splunk, Bro, etc)
    specified on the :py:class:`Edge <firewheel.control.experiment_graph.Edge>`.

    Each "collector" gets an additional IP network in order to have
    the mirrored traffic from the taps GRE tunneled to it. Each
    tunnel gets its own interface of the form ``tap<integer>`` where
    integer is the GRE key. For example, if there is a tunnel between
    the "collector" and a tap using a GRE key of 1000 then the "collector"
    will have an interface named ``tap1000``. The ``tapX`` interfaces should then
    be listened on by the collecting software (i.e Bro).
    """

    def run(self, collector_network="10.100.0.0/16"):  # noqa: DOC502
        """
        Walk the graph and drop in passive taps on links that
        have been specified to be tapped.

        Args:
            collector_network (str, optional): IP space to pull subnets from.
                The subnets are added to the various collectors and
                associated taps in order to tunnel mirrored traffic
                to the collector. Defaults to ``'10.100.0.0/16'``.

        Raises:
            RuntimeError: If the collector specified on the
                :py:class:`Edge <firewheel.control.experiment_graph.Edge>` is not a name of the
                collector :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` nor the
                actual :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` object.
        """
        collector_networks = IPNetwork(collector_network)
        # Pull /24 subnets out of the larger network
        subnets = collector_networks.subnet(24)

        def _has_collectors(edge):
            # Collectors will be saved as the `tap` attribute of the edge
            return bool(getattr(edge, "tap", False))

        # Get all original edges with collectors (before modifying any edges)
        for edge in list(filter(_has_collectors, self.g.get_edges())):
            network = next(subnets)
            collectors = edge.tap
            _EdgeTapper(edge, network).tap_edge(collectors)


class _EdgeTapper:
    """
    A transient object used to tap an
    :py:class:`Edge <firewheel.control.experiment_graph.Edge>`.
    """

    _gre_key = 1000

    def __init__(self, edge, network):
        """Initialize the Object.

        Arguments:
            edge (Edge): The edge to tap.
            network (netaddr.IPNetwork): The network used by the tap VM and
                the associated collectors.

        Attributes:
            _gre_key (int): The initial GRE tunnel key to use.
            _g (ExperimentGraph): The NetworkX graph for the given edge.
            tapped_edge (Edge): The edge to tap.
            network (netaddr.IPNetwork): The network used by the tap VM and
                the associated collectors.
            _ips (iter): An iterator for all the IP addresses in ``network``.
            _bridge_name (str): The default name of the bridge. Initially ``"br0"``.
            _tunnel_params (list): Any additional GRE tunnel parameters that are needed/used.
        """
        self._g = edge.source.g
        self.tapped_edge = edge
        self.network = network
        self._ips = network.iter_hosts()
        # Add network info for the tap
        self._bridge_name = "br0"
        self._tunnel_params = []

    def tap_edge(self, collectors):
        """
        Tap the edge using all of the collectors.

        For each tapped edge, break the current link and drop in the
        passive tap. Then hook up the link through the tap. Each tap
        then mirrors the traffic through a GRE tunnel back to the
        collector that was specified on the edge.

        Args:
            collectors (list): A list of `Vertex` objects designated to
                tap the edge.
        """
        # Ensure that the collectors argument is a list of `Vertex` objects / VM endpoints
        if not isinstance(collectors, (list, tuple)):
            collectors = [collectors]
        collectors = [self._validate_collector(_) for _ in collectors]
        # Determine the original switch and endpoint to be tapped
        orig_switch, endpoint = self._determine_edge_switch_and_endpoint()
        # Create the passive tap (requring an extra switch, since the
        # original link is being broken into two separate links)
        tap = self._create_tap(f"tap-{endpoint.name}")
        tap_switch = self._create_switch(f"{tap.name}.switch")
        tap_collector_switch = self._create_switch(f"{tap.name}-collectors.switch")
        # Reconstruct the physical connections to go through the tap
        self._reconstruct_edge(endpoint, orig_switch, tap, tap_switch)
        # Assign IP addresses and mirror traffic to the collectors
        tap_ip = next(self._ips)
        collector_ips = {collector: next(self._ips) for collector in collectors}
        self._mirror_traffic(tap, tap_ip, tap_collector_switch, collector_ips)

    def _validate_collector(self, collector):
        """
        Ensure that a given collector is a VM endpoint (or look it up).

        Args:
            collector (Vertex): A collector to be validated (or, if the
                collector is provided as a name, find the corresponding
                :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>`.

        Returns:
            Vertex: The validated collector vertex.

        Raises:
            RuntimeError: If the collector specified is not a name of the
                collector :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` nor the
                actual :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` object.
        """
        if isinstance(collector, str):
            collector = self._g.find_vertex(collector)
        if not collector.is_decorated_by(VMEndpoint):
            raise RuntimeError(
                "The collector specified on an `Edge` must be either the "
                "name of the collector vertex or the `Vertex` object."
            )
        return collector

    def _determine_edge_switch_and_endpoint(self):
        """
        Determine the switch and the endpoint of the edge.

        Returns:
            tuple(Switch, Vertex): A :py:data:`tuple` that contains the
            :py:class:`Edge's <firewheel.control.experiment_graph.Edge>` terminal
            :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` that is a
            :py:class:`base_objects.Switch` and the
            :py:class:`Edge's <firewheel.control.experiment_graph.Edge>` terminal
            :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` that is a VM.
        """
        if self.tapped_edge.source.is_decorated_by(Switch):
            switch = self.tapped_edge.source
            endpoint = self.tapped_edge.destination
        else:
            switch = self.tapped_edge.destination
            endpoint = self.tapped_edge.source
        return switch, endpoint

    def _create_tap(self, tap_name):
        """Create a new node that is a :py:class:`layer2.tap.Tap`.

        Args:
            tap_name (str): The name of the new :py:class:`layer2.tap.Tap`.

        Returns:
            Tap: The newly created :py:class:`layer2.tap.Tap`.
        """
        # Create the tap with the given name
        tap = Vertex(self._g, tap_name)
        tap.decorate(Tap)
        return tap

    def _create_switch(self, switch_name):
        """Create a new :py:class:`base_objects.Switch`.

        Args:
            switch_name (str): The name of the new :py:class:`base_objects.Switch`.

        Returns:
            base_objects.Switch: The new :py:class:`base_objects.Switch`.
        """
        # Create a tap switch with the given name.
        switch = Vertex(self._g, switch_name)
        switch.decorate(Switch)
        return switch

    def _reconstruct_edge(self, endpoint, orig_switch, tap, tap_switch):
        """
        Reconstruct the original edge.

        Using the the new tap switch, reconstruct the original edge so
        that it now connects the original switch to the endpoint via
        the tap and the tap switch.

        Args:
            endpoint (Vertex): The VM endpoint of the edge to be reconstructed.
            orig_switch (Vertex): The original switch terminating the edge to
                be reconstructed.
            tap (Vertex): The new VM endpoint to add into the reconstructed
                edge segments.
            tap_switch (Vertex): The new switch to add into the reconstructed
                edge segments.
        """
        _, tap_to_orig_switch_edge = tap.l2_connect(orig_switch)
        _, tap_to_tap_switch_edge = tap.l2_connect(tap_switch)
        new_edge = self._refresh_endpoint_interface(endpoint, tap_switch)
        # Copy over any qos details
        new_edge.qos = getattr(self.tapped_edge, "qos", None)
        # Make the new edges "False"
        tap_to_orig_switch_edge.decorate(FalseEdge)
        tap_to_tap_switch_edge.decorate(FalseEdge)
        new_edge.decorate(FalseEdge)

    def _refresh_endpoint_interface(self, endpoint, tap_switch):
        """
        Refresh the endpoint interface.

        Args:
            endpoint (Vertex): The VM endpoint to have it's interface
                refreshed.
            tap_switch (Vertex): The new tap switch now connected to the
                VM endpoint.

        Returns:
            Edge: The new edge created by connecting the endpoint to the tap
            switch.

        Raises:
            RuntimeError: If an interface cannot be found for tapping the
                endpoint.
        """
        interface = None
        for endpoint_interface in endpoint.interfaces.interfaces:
            if endpoint_interface.get("address") == self.tapped_edge.dst_ip:
                interface = endpoint_interface
                break
        else:
            raise RuntimeError(
                f"Could not find interface for tapping on endpoint: {endpoint.name}"
            )
        # Find the original interface, delete it, re-add with info here
        endpoint.interfaces.del_interface(interface["name"])
        new_interface_name, new_edge = endpoint.connect(
            tap_switch,
            interface["address"],
            interface["netmask"],
        )
        # Keep the original interface name. This keeps other dictionaries
        # in the vertex that depend on interface names consistent
        new_interface = endpoint.interfaces.get_interface(new_interface_name)
        new_interface["name"] = interface["name"]
        return new_edge

    def _mirror_traffic(self, tap, tap_ip, tap_collector_switch, collector_ips):
        """
        Mirror traffic along the original tapped edge to the collectors.

        Connect the tap to a "monitor" network so that mirrored traffic
        can be tunneled to the collector. In theory this could go over
        the same network that already exists, but you run the risk of
        tapping other mirrored traffic at upstream taps, therefore it's
        best to isolate mirrored traffic to its own network.

        Args:
            tap (Vertex): The tap VM from which traffic is mirrored.
            tap_ip (netaddr.IPAddress): The IP address of the tap VM on
                the collector subnet.
            tap_collector_switch (Vertex): The switch connecting the tap
                VM to the collectors.
            collector_ips (dict): A dictionary mapping collector vertices
                to their IP address in the subnet defined for this tap.

        """
        tap.l2_mitm(self._bridge_name)
        tap.connect(tap_collector_switch, tap_ip, self.network.netmask)
        # Connect each collector into the specified tap subnet
        self._tunnel_params = []
        for collector, collector_ip in collector_ips.items():
            collector.connect(tap_collector_switch, collector_ip, self.network.netmask)
            # Set up the GRE tunnel endpoint on the collector
            self._set_up_gre_tunnel_endpoint(collector, collector_ip, tap_ip)
        tap.mirror_traffic(self._bridge_name, *self._tunnel_params)

    def _set_up_gre_tunnel_endpoint(self, collector, collector_ip, tap_ip):
        """
        Add the tap via the GRE tunnel endpoint.

        Args:
            collector (Vertex): The collector on which to set the tap.
            collector_ip (netaddr.IPAddress): The IP of the collector
                vertex in the subnet defined for this tap.
            tap_ip (netaddr.IPAddress): The IP of the tapping VM in the
                subnet defined for this tap.
        """
        collector.run_executable(
            -100,
            "ip",
            f"link add tap{self._gre_key} type gretap key {self._gre_key} "
            f"local {collector_ip} remote {tap_ip} ttl 255",
        )
        collector.run_executable(-99, "ip", f"link set dev tap{self._gre_key} up")
        collector.run_executable(-98, "ip", f"link set tap{self._gre_key} promisc on")
        self._tunnel_params.append((collector_ip, self._gre_key))
        # Increment the GRE tunnel key
        self._gre_key += 1
