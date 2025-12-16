import yaml
import base64
from nativeedge import ctx
from nativeedge.state import ctx_parameters as inputs
from nativeedge.exceptions import NonRecoverableError

template = inputs.get("template")
parameters = inputs.get("parameters")
if not parameters.get("use_dhcp"):
    if not parameters.get("gateway"):
        raise NonRecoverableError('If dhcp not used, gateway must be provided.')
    if not parameters.get("static_ip"):
        raise NonRecoverableError('If dhcp not used, static_ip must be provided.')
if parameters.get("add_second_nic"):
    if not parameters.get("use_dhcp2"):
        if not parameters.get("static_ip2"):
            raise NonRecoverableError('If dhcp not used, static_ip must be provided.')

ctx.logger.debug(f'Generating inputs: {template}, {parameters}')

content = ctx.get_resource_and_render(resource_path=template,
                                      template_variables=dict(parameters))
netplan_encoded = base64.b64encode(content)

ctx.instance.runtime_properties['template_resource_config'] = \
    yaml.load(content.decode('utf-8'), Loader=yaml.Loader)
ctx.instance.runtime_properties['netplan_encoded'] = netplan_encoded.decode('utf-8')