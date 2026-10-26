#!/bin/sh
# Runs once at first boot (cloud-init runcmd, before netplan apply). Installs
# the pinned netplan: every NIC present now is matched by its MAC and renamed
# to a role name (data0, data1, mgmt0), so a NIC added by a later deployment
# update keeps its kernel name and can't take over the management NIC's name
# and config. If anything doesn't match the expected layout, the original
# netplan is kept.
TMPL=/etc/netplan-pinned.yaml.tmpl
OUT=/etc/netplan/50-cloud-init.yaml
WORK=/run/netplan-pinned.yaml
PAIRS="{{ 'enp1s0:data0 enp2s0:data1 enp3s0:mgmt0' if add_second_nic else 'enp1s0:data0 enp2s0:mgmt0' }}"

log() { echo "pin-nic-names: $*"; logger -t pin-nic-names "$*"; }

[ -f "$TMPL" ] || { log "no pinned template, nothing to do"; exit 0; }

expected=$(echo $PAIRS | wc -w)
present=$(ls -d /sys/class/net/en* 2>/dev/null | wc -l)
if [ "$present" -ne "$expected" ]; then
  log "found $present NICs, expected $expected; keeping the original netplan"
  exit 0
fi

cp "$TMPL" "$WORK"
for pair in $PAIRS; do
  kernel=${pair%%:*}
  role=${pair#*:}
  mac=$(cat "/sys/class/net/$kernel/address" 2>/dev/null)
  if [ -z "$mac" ]; then
    log "$kernel not found; keeping the original netplan"
    exit 0
  fi
  sed -i "s/__MAC_${role}__/$mac/" "$WORK"
  log "$kernel ($mac) -> $role"
done

install -m 600 "$WORK" "$OUT"
rm -f "$TMPL" "$WORK"
# Keep cloud-init from rewriting the pinned netplan on later boots.
printf 'network: {config: disabled}\n' > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
log "pinned netplan installed; netplan apply renames the NICs"
