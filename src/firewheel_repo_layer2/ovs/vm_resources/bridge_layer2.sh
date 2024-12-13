#!/bin/bash

BRIDGE=$1

ovs-vsctl --may-exist add-br $BRIDGE
ip link set dev $BRIDGE up

# Shift off the first arg since it's the bridge name
shift

# All the other args are the passed in MAC addresses
for mac in "$@";
do
    interface=$(ip -o link | grep ${mac} | awk '{print $2}' | sed 's/://')
    if [[ ! -z $interface ]]; then
        ovs-vsctl --may-exist add-port $BRIDGE $interface
        ip link set dev $interface up
    fi
done
