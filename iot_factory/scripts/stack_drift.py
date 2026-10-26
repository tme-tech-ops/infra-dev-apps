"""Day-2 drift for deploy_stack (desired-state).

action=check_drift: compares the desired stack settings (the non-secret
run_data, evaluated with the update's new inputs) with the settings the last
successful run applied, and returns the difference with ctx.returns. A
difference makes the update workflow run deploy_stack's update (the plugin
re-runs deploy_stack.yaml). Nothing on the host is touched, so the check needs
no SSH session.

action=record: stores the settings as applied. Runs after a successful install
(poststart) and after an update's verify_demo (postupdate), so a failed run is
retried by the next update.

The ansible-plugin's own check_drift is not used: it gathers facts with an
ad-hoc 'setup' run that does not get through the Endpoint proxy.
"""
from datetime import datetime

from dell import ctx
from dell.state import ctx_parameters as inputs

KEY = "applied_settings"


def check_drift():
    desired = inputs.get("settings") or {}
    applied = ctx.instance.runtime_properties.get(KEY)
    if applied is None:
        lines = ["no applied settings recorded (deployed before 4.2.0): re-running deploy_stack"]
    else:
        lines = [f"{key}: {applied.get(key)!r} -> {value!r}"
                 for key, value in sorted(desired.items()) if applied.get(key) != value]
    if not lines:
        ctx.logger.info("deploy_stack: no drift")
        ctx.returns(None)
        return
    ctx.logger.info("deploy_stack drift: " + "; ".join(lines))
    ctx.returns({
        "resource_id": ctx.instance.id,
        "diff_count": len(lines),
        "diff": "\n".join(lines),
        "state_drift": None,
        "time": datetime.now().isoformat(timespec="microseconds"),
    })


def record():
    # Top-level key: nested runtime-property writes are lost in update operations.
    ctx.instance.runtime_properties[KEY] = dict(inputs.get("settings") or {})
    ctx.instance.update()
    ctx.logger.info("deploy_stack: applied settings recorded")


{"check_drift": check_drift, "record": record}[inputs["action"]]()
