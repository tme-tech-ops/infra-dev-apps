#!/bin/bash

INTERFACE="enp1s0"

function wait_for_ip() {
  VM_IP=$(ip -4 a s ${INTERFACE} | awk '/inet/ {print $2}' | cut -d'/' -f1)
  timeout=$1
  shift 1
  until [ $timeout -le 0 ] || [ ! -z "$VM_IP" ]; do
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

VM_IP=$(ip -4 a s ${INTERFACE} | awk '/inet/ {print $2}' | cut -d'/' -f1)
ctx logger info "Found IP: ${VM_IP}"
ctx instance runtime-properties capabilities.vm_public_ip "$VM_IP"
