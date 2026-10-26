#!/bin/bash

# The first data NIC is data0 once pin_nic_names.sh has pinned the NIC
# names, and enp1s0 before that (or on VMs created without pinning).
function data_nic() {
  if [ -e /sys/class/net/data0 ]; then echo data0; else echo enp1s0; fi
}

function wait_for_ip() {
  INTERFACE=$(data_nic)
  VM_IP=$(ip -4 a s ${INTERFACE} | awk '/inet/ {print $2}' | cut -d'/' -f1)
  timeout=$1
  shift 1
  until [ $timeout -le 0 ] || [ ! -z "$VM_IP" ]; do
    INTERFACE=$(data_nic)
    VM_IP=$(ip -4 a s ${INTERFACE} | awk '/inet/ {print $2}' | cut -d'/' -f1)
    sleep 10
    timeout=$((timeout - 10))
  done
  if [ $timeout -le 0 ]; then
    echo 1
  fi
}

ip_not_ready=$(wait_for_ip 30)
if [ $ip_not_ready ]; then
  ctx logger error "Waiting for IP assignment.. Timeout exceeded."
  exit 1
fi

INTERFACE=$(data_nic)
VM_IP=$(ip -4 a s ${INTERFACE} | awk '/inet/ {print $2}' | cut -d'/' -f1)
ctx logger info "Found IP: ${VM_IP} on ${INTERFACE}"
# Top-level key: a nested key (capabilities.vm_public_ip) is not saved when
# this runs as a deployment-update operation, so the IP would go stale.
ctx instance runtime-properties vm_public_ip "$VM_IP"
