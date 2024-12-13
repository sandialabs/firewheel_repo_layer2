.. _layer2.tap_mc:

##########
layer2.tap
##########

This Model Component provides the capability to insert a passive tap on any link within an experiment.
This use case is explicitly for cases where the collector/analysis platform is placed within the experiment.
Examples of collectors include `Zeek <https://zeek.org>`_, `Splunk <https://www.splunk.com>`_, `Elastic Stack <https://www.elastic.co>`_, etc.

This Model Component walks the graph looking for :py:class:`Edges <firewheel.control.experiment_graph.Edge>` that have the ``tap`` attribute set.
Specifically, the ``tap`` attribute on the :py:class:`Edge <firewheel.control.experiment_graph.Edge>` must specify a list of collectors that will receive the mirrored traffic.
The list of of collectors can contain either the actual :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` object (recommended) or the name of the collector :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>`.

Once all tapped :py:class:`Edges <firewheel.control.experiment_graph.Edge>` are found, an additional IP network is added to all the specified collectors.
Each collector gets its own IP subnet to communicate to its associated taps.
This isolates the mirrored traffic from flowing over other taps in the experiment and thus eliminates the risk of accidentally duplicating traffic.

The following is the process that this model component follows to insert taps:

* Tap objects are created from :py:class:`layer2.ovs.OpenvSwitch` objects, which are :py:class:`Ubuntu1604Server <linux.ubuntu1604.Ubuntu1604Server>` with `Open vSwitch <https://www.openvswitch.org>`_ (OVS) installed.
* The specified link is then "broken" and reconnected at layer 2 through the tap object.
  The original edge is maintained to show the original logical connection between the two nodes.
  The new edges created are also decorated with :py:class:`base_objects.FalseEdge`.
* OVS is then set to create a bridge and add all layer 2 interfaces are added to the specified bridge.

  * This provides a place where the traffic can be mirrored or even man-in-the-middled if desired.

* A new "monitor" network is added to the collector and all taps associated with that collector
* GRE tunnel endpoints are created on both the tap and the collector.

  * This is the mechanism that delivers the mirrored traffic to the collector.

**Attribute Depends:**
    * ``graph``

**Attribute Provides:**
    * ``tap``

**Model Component Dependencies:**
    * :ref:`base_objects_mc`
    * :ref:`layer2.ovs_mc`
    * :ref:`generic_vm_objects_mc`

******
Plugin
******

.. automodule:: layer2.tap_plugin
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__

*****************
Available Objects
*****************

.. automodule:: layer2.tap
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__,__init__
