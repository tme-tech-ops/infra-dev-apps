"""Day-2 operations for the Site IT Toolkit compose stack.

The blueprint picks the behaviour with the `action` operation input:

  check_drift   nativeedge_compose check_drift (read-only): the compose
                substituted with the desired inputs vs the one the plugin last
                sent, plus the state of the stack's containers.
  recreate_gate nativeedge_compose update: raises on purpose, so the update
                workflow recreates the stack with the new settings (the DDPC
                Compute Service has no in-place compose update).
  postupdate    read-only summary.

Same design as compose_app (compose_app/scripts/compose_ops.py), which was
tested against the plugin on EdgeOS 4.3: the plugin substitutes the
environment into the compose itself and stores only the result
(compose_config.definition.compose, base64), and named volumes survive a
recreate.
"""
import base64
import hashlib
import json
import os
import re
from datetime import datetime

import requests

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.state import ctx_parameters as inputs

_VAR_BRACED = re.compile(r"(?<!\\)\$\{([A-Za-z0-9_]+)((:?-)([^}]+))?\}")
_VAR_BARE = re.compile(r"(?<!\\)\$([A-Za-z0-9_]+)((:?-)([^}]+))?")

# Updatable inputs and the compose variable each one sets.
INPUT_VARS = {
    "site_name": "SITE_NAME", "alert_topic": "ALERT_TOPIC", "web_check_url": "WEB_CHECK_URL",
    "dns_check_server": "DNS_CHECK_SERVER", "dns_check_name": "DNS_CHECK_NAME",
    "key_service_name": "KEY_SERVICE_NAME", "key_service_url": "KEY_SERVICE_URL",
    "check_interval": "CHECK_INTERVAL", "status_port": "STATUS_PORT", "alerts_port": "ALERTS_PORT",
    "speedtest_port": "SPEEDTEST_PORT", "toolbox_port": "TOOLBOX_PORT", "image_registry": "IMAGE_REGISTRY",
}


def envsubst(text, env):
    def repl(match):
        var, default = match.group(1), match.group(4)
        if var in env:
            return env[var]
        if default is not None:
            return default
        return match.group(0)
    return _VAR_BARE.sub(repl, _VAR_BRACED.sub(repl, text))


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _pending_inputs():
    """New inputs of the deployment update driving this execution, if any.

    During an update *preview* the operation inputs still resolve against the
    old deployment inputs; the update record carries the new values.
    """
    if ctx.workflow_id != "update":
        return {}
    try:
        from dell import manager
        client = manager.get_rest_client()
        for update in client.deployment_updates.list(deployment_id=ctx.deployment.id):
            if update.get("execution_id") == ctx.execution_id:
                return update.get("new_inputs") or {}
    except Exception as err:
        ctx.logger.info(f"Could not read the deployment update record ({err}); using operation inputs")
    return {}


def _desired_compose():
    env = {k: str(v) for k, v in (inputs.get("environment") or {}).items()}
    for name, value in _pending_inputs().items():
        if name in INPUT_VARS and value is not None:
            env[INPUT_VARS[name]] = str(value)
    # The compose file of the current blueprint revision (not the copy
    # prepare_compose_yaml stored at install), so a revision that changes it
    # shows up as drift.
    filename = ctx.download_resource(inputs.get("compose_file"))
    with open(filename) as f:
        return envsubst(f.read(), env)


def _applied_compose():
    encoded = ((ctx.instance.runtime_properties.get("compose_config") or {})
               .get("definition") or {}).get("compose")
    return base64.b64decode(encoded).decode() if encoded else None


def _live_containers():
    """The stack's containers from the Compute Service, or None if unavailable."""
    deployment_id = ctx.instance.runtime_properties.get("deployment_id")
    try:
        token, initiator = ctx.edge_estate_token, ctx.edge_estate_initiator_token
    except Exception as err:
        ctx.logger.info(f"Container state unavailable (no edge estate token in script ctx: {err})")
        return None
    if not token or not deployment_id:
        return None
    host = os.getenv("EO_URL", "internal-ingress-gateway.istio-system.svc.cluster.local")
    resp = requests.get(f"http://{host}/compute/api/v2/containers?search=deployment_id:{deployment_id}",
                        headers={"x-edge-estate-auth": token, "x-edge-estate-initiator": initiator}, timeout=30)
    if not resp.ok:
        ctx.logger.warning(f"Container state unavailable (HTTP {resp.status_code} from Compute Service)")
        return None
    current = {}
    for container in resp.json().get("results") or []:
        extra = container.get("extra") or {}
        if isinstance(extra.get("data"), dict):
            container = {**container, **extra["data"]}
        current[container.get("containerName")] = container
    return current


def _state(info):
    for key in ("state", "status", "containerState"):
        if isinstance(info, dict) and info.get(key) is not None:
            return str(info.get(key))
    return None


def check_drift():
    lines = []
    desired, applied = _desired_compose(), _applied_compose()
    if applied is None:
        lines.append("# no applied compose recorded")
    elif sha256(desired) != sha256(applied):
        lines.append("# settings changed")
    current = _live_containers()
    expected = ctx.instance.runtime_properties.get("expected_containers") or {}
    if current is not None:
        for name in sorted(set(expected) | set(current)):
            if name not in current:
                lines.append(f"# container missing: {name}")
            elif name not in expected:
                lines.append(f"# unexpected container: {name}")
            elif _state(current[name]) != _state(expected[name]):
                lines.append(f"# container {name} state {_state(expected[name])} -> {_state(current[name])}")
    if not lines:
        ctx.logger.info("nativeedge_compose: no drift")
        ctx.returns(None)
        return
    ctx.logger.info("nativeedge_compose drift: " + "; ".join(lines))
    ctx.returns({
        "resource_id": ctx.instance.id,
        "diff_count": len(lines),
        "diff": "\n".join(lines),
        "state_drift": None,
        "time": datetime.now().isoformat(timespec="microseconds"),
    })


def recreate_gate():
    raise NonRecoverableError(
        "EXPECTED: the DDPC Compute Service has no in-place compose update, so this update "
        "intentionally fails and the update workflow recreates the stack with the new settings "
        "(delete + create; named volumes are kept). This needs 'Run automatic reinstall' checked; "
        "without it the update stops here and the stack keeps its old settings.")


def postupdate():
    applied = _applied_compose()
    ctx.logger.info(f"postupdate {ctx.node.id}: " + json.dumps({
        "applied_compose_sha256": sha256(applied) if applied else None,
        "expected_containers": sorted((ctx.instance.runtime_properties.get("expected_containers") or {}).keys()),
    }))


ACTIONS = {"check_drift": check_drift, "recreate_gate": recreate_gate, "postupdate": postupdate}

action = inputs.get("action")
if action not in ACTIONS:
    raise NonRecoverableError(f"toolkit_ops: unknown action '{action}'")
ACTIONS[action]()
