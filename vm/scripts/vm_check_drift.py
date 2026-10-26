"""check_drift for the VM (replaces the edge-plugin's).

The edge-plugin's check_drift always reports drift, so every deployment update
sends the VM an update even when nothing about the VM changed (for example an
iot_factory setting). The Endpoint sometimes never completes such a no-op
update, and update_apply then polls for up to an hour.

This compares the desired vm_config (the node properties, evaluated with the
update's inputs) with expected_configuration, the config the edge-plugin
stored after the last successful create or update, field by field over
everything the plugin sends in an update. No difference: no drift, and the VM
update is skipped. Any difference, or anything it can't compare: drift, and
the plugin updates the VM as before. Read-only.
"""
import json
import re
from datetime import datetime

from dell import ctx

UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}


def to_bytes(size):
    if isinstance(size, int):
        return size
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]B)\s*", str(size or "").upper())
    return int(float(match.group(1)) * UNITS[match.group(2)]) if match else size


def canonical(config):
    """The fields the edge-plugin sends in a VM update, in one comparable form."""
    limits = config.get("resource_constraints") or {}
    ports = config.get("ports") or {}
    return {
        "name": config.get("name"),
        "cpu": limits.get("cpu"),
        "memory": to_bytes(limits.get("memory")),
        "storage": to_bytes(limits.get("storage")),
        "controller": str(limits.get("controller") or "").upper(),
        "disconnect_flag": bool((config.get("main_disk") or {}).get("disconnect_flag")),
        "network_settings": sorted(
            json.dumps({"name": n.get("name"), "segment_name": n.get("segment_name"),
                        "model_type": n.get("model_type") or "VIRTIO",
                        "port_fwd_rules": n.get("port_fwd_rules") or []}, sort_keys=True)
            for n in config.get("network_settings") or []),
        "ports": {k: sorted(json.dumps(p, sort_keys=True) for p in ports.get(k) or [])
                  for k in ("usb", "serial_port", "gpu", "video", "pcie")},
        "boot_order": list(config.get("boot_order") or []),
        "additional_disks": sorted(
            json.dumps({"name": d.get("name"), "disk": d.get("disk"),
                        "size": to_bytes(f"{d.get('storage')}{str(d.get('storage_unit') or 'GB').upper()}")},
                       sort_keys=True)
            for d in config.get("additional_disks") or []),
        "custom_parameters": config.get("custom_parameters") or {},
        "advanced_hypervisor_parameters": config.get("advanced_hypervisor_parameters") or {},
    }


def drift(lines):
    ctx.logger.info("vm drift: " + "; ".join(lines))
    ctx.returns({
        "resource_id": "vm_config",
        "diff_count": len(lines),
        "diff": "\n".join(lines),
        "state_drift": None,
        "time": datetime.now().isoformat(timespec="microseconds"),
    })


def main():
    expected = ctx.instance.runtime_properties.get("expected_configuration")
    if not expected:
        drift(["no expected_configuration recorded by the edge-plugin"])
        return
    try:
        desired, applied = canonical(ctx.node.properties["vm_config"]), canonical(expected)
    except Exception as err:  # can't compare: let the plugin update the VM
        drift([f"could not compare the VM config ({err})"])
        return
    lines = [f"{key}: {applied[key]!r} -> {desired[key]!r}" for key in desired if desired[key] != applied[key]]
    if lines:
        drift(lines)
    else:
        ctx.logger.info("vm: no drift (the VM config is unchanged)")
        ctx.returns(None)


main()
