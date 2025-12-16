from nativeedge import ctx
from nativeedge.state import ctx_parameters as inputs

network_segments = inputs.get('network_segments')
port_forwards = inputs.get('port_forwards')
network_settings = []

for idx, network in enumerate(network_segments):
    ctx.logger.debug(f'Processing network: {network}')
    if network:
        iface = 'VNIC0' if idx == 0 else f'VNIC{idx}'
        network_setting = {
            'name': iface,
            'segment_name': network
        }
        
        # Add port forwards if available
        if port_forwards and idx < len(port_forwards):
            network_setting['port_fwd_rules'] = port_forwards[idx]
        
        network_settings.append(network_setting)
    else:
        ctx.logger.debug('Skipping - no network segment to attach.')

ctx.logger.debug(f'Number of VNICs attached: {len(network_settings)}')

ctx.instance.runtime_properties['network_settings'] = network_settings