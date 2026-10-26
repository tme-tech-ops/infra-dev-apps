"""Resolves the Endpoint proxy (eo-proxy) address of the VM's SSH port.

Runs right before each Ansible run on a DDPC VM (precreate before start at
install, preupdate before update, prestop before stop) and stores the address
as the runtime properties proxy_host / proxy_port, which the inventory reads.

Why not the ansible-plugin's inventory_proxy_settings: the plugin resolves a
new address at the start of every run, after the run's inventory has already
been evaluated from the previous address. When the new lookup returns a
different proxy service, the old one is released and the run can't connect
(seen on deployment updates). With one lookup here and none in the plugin,
the run always uses a live address.
"""
import os

import requests

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.state import ctx_parameters as inputs

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://hzp-inventory-svc:80").rstrip("/")


def get_json(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=60)
    except requests.RequestException as err:
        raise NonRecoverableError(f"Inventory service request failed: {err}")
    if response.status_code != 200:
        raise NonRecoverableError(f"Inventory service returned HTTP {response.status_code} for {url}")
    return response.json()


def target_id(service_tag):
    data = get_json(f"{INVENTORY_URL}/api/v2/endpoints?search=external_id={service_tag}&only=id")
    results = data if isinstance(data, list) else data.get("results") or []
    if not results or not results[0].get("id"):
        raise NonRecoverableError(f"No Endpoint found for service tag '{service_tag}'")
    return results[0]["id"]


def main():
    service_tag = inputs.get("service_tag")
    vm_name = inputs.get("vm_name")
    port = inputs.get("port", 22)
    if not service_tag or not vm_name:
        raise NonRecoverableError("service_tag and vm_name are required")
    data = get_json(f"{INVENTORY_URL}/api/i1/endpoints/{target_id(service_tag)}/connection"
                    "?type=direct&interfaceType=OOB", params={"ip": vm_name, "port": port})
    host, resolved_port = data.get("host"), data.get("port")
    if not host or not resolved_port:
        raise NonRecoverableError(f"No proxy address returned for {vm_name}:{port}")
    # Top-level keys: nested runtime-property writes are lost in update operations.
    ctx.instance.runtime_properties["proxy_host"] = host
    ctx.instance.runtime_properties["proxy_port"] = int(resolved_port)
    ctx.instance.update()
    ctx.logger.info(f"Endpoint proxy address for {vm_name}:{port}: {host}:{resolved_port}")


main()
