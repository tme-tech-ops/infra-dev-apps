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

def render(resource_path, **extra):
    return ctx.get_resource_and_render(resource_path=resource_path,
                                       template_variables=dict(parameters, **extra))


# First-boot netplan (kernel names), plus the pinned version and the script
# that installs it at first boot (see vm/templates/pin_nic_names.sh).
content = render(template, pinned=False)
pinned = render(template, pinned=True)
pin_script = render(inputs.get("pin_script"))
yaml.safe_load(pinned.decode('utf-8'))  # fail early if invalid

ctx.instance.runtime_properties['template_resource_config'] = \
    yaml.safe_load(content.decode('utf-8'))
ctx.instance.runtime_properties['netplan_encoded'] = base64.b64encode(content).decode('utf-8')
ctx.instance.runtime_properties['netplan_pinned_encoded'] = base64.b64encode(pinned).decode('utf-8')
ctx.instance.runtime_properties['pin_script_encoded'] = base64.b64encode(pin_script).decode('utf-8')