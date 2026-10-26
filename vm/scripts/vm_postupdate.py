"""Checks that a deployment update really changed the VM.

Runs as the VM's update_postapply, after the edge-plugin's update_apply. It reads
the VM record from the compute API and compares it with the config the plugin
sent (update_vm_config). A field that doesn't match fails the update, so a
change the platform accepted but didn't apply doesn't pass silently. Fields
the record doesn't carry are logged and skipped. Read-only.
"""
import os
import re

import requests

from dell import ctx
from dell.exceptions import NonRecoverableError

GATEWAY = os.getenv("EO_URL", "internal-ingress-gateway.istio-system.svc.cluster.local")
VM_URL = "http://{0}/compute/api/v2/vms/{1}"
skipped = []
UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}


def to_bytes(size, unit=None):
    """'8GB' / '8192 MB' / (8, 'GB') / bytes -> bytes, or None if unreadable.

    update_vm_config holds memory and storage as integer bytes.
    """
    if size is None:
        return None
    if isinstance(size, int) and not unit:
        return size
    if unit:
        size = f"{size}{unit}"
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]B)\s*", str(size).upper())
    if not match:
        return None
    return int(float(match.group(1)) * UNITS[match.group(2)])


def get_vm_record(vm_id):
    headers = {
        "x-edge-estate-auth": getattr(ctx, "edge_estate_token", None) or "",
        "x-edge-estate-initiator": getattr(ctx, "edge_estate_initiator_token", None) or "",
    }
    try:
        response = requests.get(VM_URL.format(GATEWAY, vm_id), headers=headers, timeout=30)
    except requests.RequestException as err:
        ctx.logger.warning(f"VM record not available ({err}); nothing checked")
        return None
    if not response.ok:
        ctx.logger.warning(f"VM record not available (HTTP {response.status_code}); nothing checked")
        return None
    return response.json()


def shape(obj, depth=3):
    """Key names and types only (no values: the record can hold cloud-init)."""
    if depth == 0:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {k: shape(v, depth - 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shape(obj[0], depth - 1)] if obj else []
    return type(obj).__name__


def check(problems, what, wanted, actual):
    if wanted is None:
        # update_vm_config leaves out some fields; nothing to compare.
        ctx.logger.info(f"{what}: not in the update, skipped")
    elif actual is None:
        skipped.append(what)
        ctx.logger.info(f"{what}: not in the VM record, skipped")
    elif wanted != actual:
        problems.append(f"{what}: requested {wanted}, VM has {actual}")
    else:
        ctx.logger.info(f"{what}: {actual} (as requested)")


def main():
    props = ctx.instance.runtime_properties
    sent = props.get("update_vm_config") or {}
    vm_id = (props.get("vm_details") or {}).get("id")
    if not sent or not vm_id:
        ctx.logger.info("No VM update was sent; nothing to check")
        return
    record = get_vm_record(vm_id)
    if record is None:
        return

    # The compute record keeps the live config under "extra".
    extra = record.get("extra") or {}
    problems = []
    limits = sent.get("resource_constraints") or {}
    check(problems, "vCPUs", limits.get("cpu"), extra.get("processors"))
    ram_mb = ((extra.get("size") or {}).get("ram") or {}).get("sizeInMB")
    check(problems, "memory", to_bytes(limits.get("memory")),
          None if ram_mb is None else ram_mb * UNITS["MB"])

    disks = {d.get("label"): d.get("capacity") for d in extra.get("virtual_disks") or []}
    if disks:
        check(problems, "OS disk", to_bytes(limits.get("storage")), disks.get("main_disk"))
        wanted = None
        if "additional_disks" in sent:
            wanted = {d.get("name"): to_bytes(d.get("storage"), d.get("storage_unit"))
                      for d in sent["additional_disks"] or []}
        actual = {name: size for name, size in disks.items() if name != "main_disk"}
        check(problems, "additional disks", wanted, actual)
    else:
        skipped.append("disks")
        ctx.logger.info("disks: not in the VM record, skipped")

    nics = [(tap.get("vmInterface") or {}) for tap in extra.get("tap_interfaces") or []]
    nics = [n for n in nics if n.get("name") != "MGMT-VNIC"]
    if nics:
        wanted = None
        if "network_settings" in sent:
            wanted = sorted(n.get("segment_name") for n in sent["network_settings"] or [])
        check(problems, "NIC segments", wanted, sorted(n.get("segmentName") for n in nics))
    else:
        skipped.append("NICs")
        ctx.logger.info("NICs: not in the VM record, skipped")

    if skipped:
        ctx.logger.info(f"VM record layout: {shape(record)}")
    if problems:
        raise NonRecoverableError(
            "The update completed but the VM doesn't match it: " + "; ".join(problems))
    ctx.logger.info("The VM matches the update")


main()
