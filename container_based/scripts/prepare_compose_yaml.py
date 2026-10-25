from dell import ctx
from dell.exceptions import NonRecoverableError

COMPOSE_FILE = "container_based/compose/site_it_toolkit.yaml"

# Read the compose file shipped in the blueprint package and hand it to the
# nativeedge_compose node as a runtime property.
filename = ctx.download_resource(COMPOSE_FILE)
if not filename:
    raise NonRecoverableError(
        f"Compose file {COMPOSE_FILE} not found in the blueprint package")

with open(filename) as f:
    ctx.instance.runtime_properties["compose_yaml"] = f.read()
ctx.instance.update()
