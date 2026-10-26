"""Loads the compose file shipped in the blueprint into a runtime property.

action=load (start, update): store the file as compose_yaml for the
nativeedge_compose node.
action=check_drift: the file in the current blueprint revision vs the stored
copy, so a new revision with a changed compose file is picked up.
"""
from datetime import datetime

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.state import ctx_parameters as inputs

COMPOSE_FILE = "site_it_toolkit/compose/site_it_toolkit.yaml"


def read_compose():
    filename = ctx.download_resource(COMPOSE_FILE)
    if not filename:
        raise NonRecoverableError(
            f"Compose file {COMPOSE_FILE} not found in the blueprint package")
    with open(filename) as f:
        return f.read()


action = inputs.get("action") or "load"
if action == "check_drift":
    if read_compose() == ctx.instance.runtime_properties.get("compose_yaml"):
        ctx.logger.info("prepare_compose_yaml: no drift")
        ctx.returns(None)
    else:
        ctx.logger.info("prepare_compose_yaml: the compose file changed")
        ctx.returns({"resource_id": ctx.instance.id, "diff_count": 1,
                     "diff": f"{COMPOSE_FILE} changed", "state_drift": None,
                     "time": datetime.now().isoformat(timespec="microseconds")})
else:
    ctx.instance.runtime_properties["compose_yaml"] = read_compose()
    ctx.instance.update()
