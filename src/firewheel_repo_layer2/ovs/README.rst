.. _layer2.ovs_mc:

##########
layer2.ovs
##########

This Model Component contains functionality to install `Open vSwitch <https://www.openvswitch.org/>`__ on an :py:class:`Ubuntu1604Server <linux.ubuntu1604.Ubuntu1604Server>` endpoint.
Open vSwitch is useful for many applications.
Specific use cases include transparent firewalls and passive taps, among other possible applications.

**Model Component Dependencies:**
    * :ref:`linux.ubuntu1604_mc`
    * :ref:`base_objects_mc`

************
VM Resources
************
* ``openvswitch-switch.tgz`` -- A tarball containing the required debian packages for installing Open vSwitch on a Ubuntu server. Currently, the packages include: ``openvswitch-common``, ``openvswitch-switch``, and ``python-six`` (a dependency of OVS).
* ``bridge_layer2.sh`` -- A shell script to create a new OVS bridge and then create new taps on the bridge for any passed-in MAC addresses.

*****************
Available Objects
*****************

.. automodule:: layer2.ovs
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
