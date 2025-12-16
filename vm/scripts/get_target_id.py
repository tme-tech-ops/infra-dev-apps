import os
import requests

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.state import ctx_parameters as inputs

TARGET_ID_LABEL_KEY = 'target_id'
TARGET_EXTERNAL_ID_LABEL_KEY = 'target_external_id'
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://hzp-inventory-svc:80")
EOPROXY_URL = 'http://hzp-eoproxy-svc:8080/api/v1/eoproxy'


def resolve_target_id_from_inventory(external_id: str) -> str:
    """
    Queries the inventory service to resolve a target_id from an external_id.
    """
    url = (
        f"{INVENTORY_URL.rstrip('/')}/api/v2/endpoints?"
        f"search=external_id={external_id}&only=id"
    )
    ctx.logger.info(
        f"Querying inventory for external_id '{external_id}' at URL: {url}"
    )
    try:
        response = requests.get(url)
        ctx.logger.info(f"Inventory service response:"
                        f"{response.content.decode('utf-8')}")
    except Exception as e:
        ctx.logger.error(f"Error calling inventory service: {e}")
        raise NonRecoverableError(f"Inventory service request failed: {e}")

    if response.status_code == 200:
        response_json = response.json()
        if isinstance(response_json, list) and response_json:
            target_id = response_json[0].get("id")
            if target_id:
                ctx.logger.info(f"Resolved target_id '{target_id}'"
                                f"from external_id '{external_id}'")
                return target_id
            else:
                raise NonRecoverableError(
                    f"No 'id' found in inventory"
                    f"response for external_id '{external_id}'"
                )
        elif isinstance(response_json, dict) and response_json:
            target_id = response.json().get('results')[0].get("id")
            if target_id:
                ctx.logger.info(f"Resolved target_id '{target_id}'"
                                f"from external_id '{external_id}'")
                return target_id
            else:
                raise NonRecoverableError(
                    f"No 'id' found in inventory"
                    f"response for external_id '{external_id}'"
                )
        else:
            raise NonRecoverableError(f"No endpoints found for"
                                      f"external_id '{external_id}'")
    else:
        raise NonRecoverableError(
            f"Query failed with status code {response.status_code}."
            f"external_id: {external_id}"
        )


if __name__ == "__main__":
    service_tag = inputs.get("service_tag", "")
    if service_tag:
        target_id = resolve_target_id_from_inventory(service_tag)
        ctx.instance.runtime_properties['_proxy_target_id'] = target_id
        ctx.instance.runtime_properties['connection_proxy_settings'] = {
            'auto_resolve': False,
            'target_id': target_id
        }
    else:
        ctx.logger.info("No service_tag provided. Auto resolving.")
        ctx.instance.runtime_properties['_proxy_target_id'] = ''
        ctx.instance.runtime_properties['connection_proxy_settings'] = {
            'auto_resolve': True
        }
    ctx.instance.update()