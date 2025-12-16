from dell import ctx
from dell.state import ctx_parameters as inputs

def prepare_serial_ports(serial_port):
  x = serial_port.split("_")
  serial_port_dict = {}
  serial_port_dict["port"] = x[0]
  serial_port_dict["mode"] = x[1]
  return serial_port_dict

serial_port_inputs  = inputs.get('serial_port')
serial_ports_list = []
if serial_port_inputs:
    for i in serial_port_inputs:
       serial_ports_list.append(prepare_serial_ports(i))
    ctx.instance.runtime_properties['serial_ports_list'] = serial_ports_list
else:
    ctx.instance.runtime_properties['serial_ports_list'] = []