"""Compose validation, drift detection and Day-2 gating for compose_app.

A single script serves several operations; the blueprint selects the
behaviour with the `action` operation input:

  validate             compose_definition create/update: envsubst + validate,
                       publish services/published_ports/desired hash
  check_drift_def      compose_definition check_drift (read-only)
  check_drift_compose  nativeedge_compose check_drift (read-only)
  recreate_gate        nativeedge_compose update: validate, then raise so the
                       update workflow recreates the compose (no in-place API)
  postupdate           read-only post-update verification / summary

The supported surface mirrors the Compute Service v2 compose validator
(POST /compute/api/v2/composes/validate) on EdgeOS 4.3.0.0 with edge-plugin
3.3.33.0. Anything outside it is an error, reported all at once.
"""
import base64
import difflib
import hashlib
import json
import os
import re
from datetime import datetime

import yaml

from dell import ctx
from dell.state import ctx_parameters as inputs
from dell.exceptions import NonRecoverableError

# --- envsubst: copied from edge-plugin utils.envsubst_yaml so we validate
# exactly what the plugin will send.
_VAR_BRACED = re.compile(r"(?<!\\)\$\{([A-Za-z0-9_]+)((:?-)([^}]+))?\}")
_VAR_BARE = re.compile(r"(?<!\\)\$([A-Za-z0-9_]+)((:?-)([^}]+))?")

TOP_KEYS = {"services", "volumes", "version", "name"}
SERVICE_KEYS = {
    "image", "container_name", "hostname", "restart", "command", "entrypoint",
    "environment", "ports", "volumes", "devices", "depends_on", "deploy",
    "platform",
}
HINTS = {
    "privileged": "privileged containers are not supported on NativeEdge",
    "cap_add": "Linux capabilities cannot be changed on NativeEdge",
    "cap_drop": "Linux capabilities cannot be changed on NativeEdge",
    "security_opt": "security options are not supported on NativeEdge",
    "user": "running as a specific user is not supported; build it into the image",
    "network_mode": "custom networking is not supported; publish ports with 'ports'",
    "networks": "custom networks are not supported; services share the default network",
    "build": "endpoints cannot build images; push to a registry and use 'image'",
    "env_file": "use 'environment' or the Compose Environment input",
    "mem_limit": "use deploy.resources.limits.memory",
    "mem_reservation": "use deploy.resources.reservations.memory",
    "cpus": "use deploy.resources.limits.cpus",
    "expose": "use 'ports' with HOST:CONTAINER",
    "secrets": "compose secrets are not supported",
    "configs": "compose configs are not supported",
    "healthcheck": "healthchecks are not supported; bake HEALTHCHECK into the image",
    "gpus": "GPU passthrough is not supported for compose on NativeEdge",
    "include": "multi-file compose is not supported",
}

IMAGE_RE = re.compile(r"^([a-zA-Z0-9_./-]+)(:([0-9]+))?(/)([a-zA-Z0-9_./-]+)(:([a-zA-Z0-9_.-]+))?$")
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]+$")
SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
RESTART_RE = re.compile(r"^(no|always|unless-stopped|on-failure(:[1-9][0-9]*)?)$")
PORT_RE = re.compile(r"^([0-9]{1,5}):([0-9]{1,5})(/(tcp|udp))?$")
VOLUME_RE = re.compile(r"^([a-zA-Z0-9._-]+):([^:]+)(:(rw|ro|z|Z))?$")
DEVICE_RE = re.compile(r"^[^/]+:(/[^/ ]*)+$")
MEMORY_RE = re.compile(r"^(0|[1-9][0-9]*)(b|B|k|K|kb|KB|m|M|mb|MB|g|G|gb|GB)?$")
SIZE_OPT_RE = re.compile(r"^size=([1-9][0-9]*)(b|k|kb|kib|m|mb|mib|g|gb|gib|t|tb|tib)$", re.IGNORECASE)
ENV_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


class _Yaml12Loader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 core-schema scalars.

    The Compute Service parses with a YAML 1.2 parser; PyYAML's 1.1 rules
    would turn unquoted `8080:80` into a base-60 int and `restart: no` into
    False, producing false errors.
    """


_Yaml12Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v
        if tag not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:int", "tag:yaml.org,2002:float")]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:int", re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789"))
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+0123456789."))


def _input(name, default=None):
    # only_with-hidden inputs arrive as None rather than missing
    value = inputs.get(name)
    return default if value is None else value


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


def validate(text, env, registry=None):
    """Return (errors, warnings, compose_dict, substituted_text)."""
    errors, warnings = [], []
    if not text or not text.strip():
        return ["compose: definition is empty"], warnings, None, ""

    if not isinstance(env, dict):
        errors.append("compose_environment: must be a map of NAME: value")
        env = {}
    for key, value in env.items():
        if not ENV_KEY_RE.match(str(key)):
            errors.append(f"compose_environment.{key}: name must match [A-Za-z0-9_]+")
        if not isinstance(value, str):
            errors.append(f"compose_environment.{key}: value must be a string (quote it), got {type(value).__name__}")
    env = {str(k): v for k, v in env.items() if isinstance(v, str)}

    if registry and registry.get("enabled"):
        if not registry.get("url"):
            errors.append("registry_url: required when Registry Login is enabled")
        if not registry.get("secret"):
            errors.append("registry_credentials_secret: required when Registry Login is enabled")

    substituted = envsubst(text, env)
    for var in sorted({m.group(1) for m in _VAR_BRACED.finditer(substituted)}):
        errors.append(f"${{{var}}}: not set in Compose Environment and has no :-default")
    for var in sorted({m.group(1) for m in _VAR_BARE.finditer(substituted)} - set(env)):
        warnings.append(f"${var} is not substituted and will be passed literally")
    if "$$" in substituted:
        warnings.append("'$$' is passed to the container literally (NativeEdge does not apply the compose "
                        "'$$' -> '$' unescape); a shell command containing '$$(...)' will fail")

    try:
        docs = list(yaml.load_all(substituted, Loader=_Yaml12Loader))
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        return errors + [f"compose: invalid YAML{where}: {getattr(err, 'problem', err)}"], warnings, None, substituted
    if len(docs) != 1:
        return errors + ["compose: exactly one YAML document is required (no '---' separators)"], warnings, None, substituted
    data = docs[0]
    if not isinstance(data, dict):
        return errors + ["compose: top level must be a mapping"], warnings, None, substituted

    for key in data:
        if key not in TOP_KEYS and not str(key).startswith("x-"):
            errors.append(f"{key}: top-level key not supported{_hint(key)}")
    if "version" in data:
        warnings.append("version: obsolete in the Compose spec and ignored")
    if "name" in data and not isinstance(data["name"], str):
        errors.append("name: must be a string")

    declared_volumes = _check_top_volumes(data.get("volumes"), errors)

    services = data.get("services")
    if not isinstance(services, dict) or not services:
        errors.append("services: at least one service is required")
        return errors, warnings, data, substituted

    seen_ports, seen_names = {}, {}
    for name, svc in services.items():
        path = f"services.{name}"
        if not SERVICE_NAME_RE.match(str(name)):
            errors.append(f"{path}: service name must match {SERVICE_NAME_RE.pattern}")
        if not isinstance(svc, dict):
            errors.append(f"{path}: must be a mapping")
            continue
        for key in svc:
            if key not in SERVICE_KEYS and not str(key).startswith("x-"):
                errors.append(f"{path}.{key}: not supported on NativeEdge{_hint(key)}")
        _check_service(path, name, svc, services, declared_volumes, seen_ports, seen_names, errors, warnings)
    return errors, warnings, data, substituted


def _hint(key):
    return f" ({HINTS[key]})" if key in HINTS else ""


def _check_top_volumes(volumes, errors):
    if volumes is None:
        return set()
    if not isinstance(volumes, dict):
        errors.append("volumes: must be a mapping of volume names")
        return set()
    for vname, spec in volumes.items():
        if spec in (None, {}):
            continue
        if not isinstance(spec, dict):
            errors.append(f"volumes.{vname}: must be empty or a mapping")
            continue
        for key in spec:
            if key != "driver_opts":
                errors.append(f"volumes.{vname}.{key}: not supported (only driver_opts.o: size=<N><unit>)")
        opts = spec.get("driver_opts")
        if opts is not None:
            if not isinstance(opts, dict) or set(opts) - {"o"}:
                errors.append(f"volumes.{vname}.driver_opts: only 'o: size=<N><unit>' is supported")
            elif not SIZE_OPT_RE.match(str(opts.get("o", ""))):
                errors.append(f"volumes.{vname}.driver_opts.o: must be size=<N><unit>, e.g. size=1G")
    return set(volumes)


def _check_service(path, name, svc, services, declared_volumes, seen_ports, seen_names, errors, warnings):
    image = svc.get("image")
    if image is None:
        errors.append(f"{path}.image: required")
    elif not isinstance(image, str) or not IMAGE_RE.match(image):
        hint = ""
        if isinstance(image, str) and "@" in image:
            hint = " (digests are not supported; use a tag)"
        elif isinstance(image, str) and "/" not in image:
            hint = f" (include the registry/namespace, e.g. 'docker.io/library/{image}')"
        errors.append(f"{path}.image: '{image}' is not a supported image reference{hint}")

    for key in ("container_name", "hostname"):
        if key in svc:
            value = svc[key]
            if not isinstance(value, str) or not NAME_RE.match(value):
                errors.append(f"{path}.{key}: must match {NAME_RE.pattern}")
    cname = svc.get("container_name")
    if isinstance(cname, str):
        if cname in seen_names:
            errors.append(f"{path}.container_name: '{cname}' already used by service '{seen_names[cname]}'")
        seen_names[cname] = name

    if "restart" in svc and (not isinstance(svc["restart"], str) or not RESTART_RE.match(svc["restart"])):
        errors.append(f"{path}.restart: must be no, always, unless-stopped or on-failure[:N]")

    command = svc.get("command")
    if command is not None and not (isinstance(command, str) or
                                    (isinstance(command, list) and all(isinstance(c, str) for c in command))):
        errors.append(f"{path}.command: must be a string or a list of strings")
    if "entrypoint" in svc and not isinstance(svc["entrypoint"], str):
        errors.append(f"{path}.entrypoint: must be a single string (list form is not supported)")

    env = svc.get("environment")
    if env is not None:
        if isinstance(env, dict):
            for key, value in env.items():
                if isinstance(value, (dict, list)):
                    errors.append(f"{path}.environment.{key}: must be a scalar")
        elif not (isinstance(env, list) and all(isinstance(e, str) for e in env)):
            errors.append(f"{path}.environment: must be a map or a list of KEY=VALUE strings")

    _check_list(path, "ports", svc, errors)
    for i, port in enumerate(svc.get("ports") or [] if isinstance(svc.get("ports"), list) else []):
        match = PORT_RE.match(port) if isinstance(port, str) else None
        if not match:
            errors.append(f"{path}.ports[{i}]: '{port}' must be a quoted \"HOST:CONTAINER[/tcp|udp]\" string "
                          "(no IP binding, ranges, container-only ports or long syntax)")
            continue
        host, ctr, proto = int(match.group(1)), int(match.group(2)), match.group(4) or "tcp"
        if not (1 <= host <= 65535 and 1 <= ctr <= 65535):
            errors.append(f"{path}.ports[{i}]: ports must be 1-65535")
        key = (host, proto)
        if key in seen_ports:
            errors.append(f"{path}.ports[{i}]: host port {host}/{proto} already published by service '{seen_ports[key]}'")
        seen_ports[key] = name

    _check_list(path, "volumes", svc, errors)
    for i, vol in enumerate(svc.get("volumes") if isinstance(svc.get("volumes"), list) else []):
        if isinstance(vol, str) and vol[:1] in ("/", ".", "~"):
            errors.append(f"{path}.volumes[{i}]: bind mounts are not supported on NativeEdge; use a named volume")
            continue
        match = VOLUME_RE.match(vol) if isinstance(vol, str) else None
        if not match:
            errors.append(f"{path}.volumes[{i}]: must be \"name:/path[:rw|ro|z|Z]\" (short syntax, named volume)")
        elif match.group(1) not in declared_volumes:
            errors.append(f"{path}.volumes[{i}]: volume '{match.group(1)}' is not declared under top-level 'volumes'")

    _check_list(path, "devices", svc, errors)
    for i, dev in enumerate(svc.get("devices") if isinstance(svc.get("devices"), list) else []):
        if not isinstance(dev, str) or not DEVICE_RE.match(dev):
            errors.append(f"{path}.devices[{i}]: must be \"ALIAS:/dev/path\" using the endpoint peripheral "
                          "name (e.g. COM-1:/dev/ttyS0)")

    if "depends_on" in svc:
        deps = svc["depends_on"]
        if not isinstance(deps, list):
            errors.append(f"{path}.depends_on: must be a list of service names (condition maps are not supported)")
        else:
            for dep in deps:
                if dep == name:
                    errors.append(f"{path}.depends_on: a service cannot depend on itself")
                elif dep not in services:
                    errors.append(f"{path}.depends_on: unknown service '{dep}'")

    if "deploy" in svc:
        _check_deploy(path, svc["deploy"], errors)

    if "platform" in svc and not isinstance(svc["platform"], str):
        errors.append(f"{path}.platform: must be a string")


def _check_list(path, key, svc, errors):
    if key in svc and not isinstance(svc[key], list):
        errors.append(f"{path}.{key}: must be a list")


def _check_deploy(path, deploy, errors):
    allowed = {"limits": {"cpus", "memory"}, "reservations": {"memory"}}
    if not isinstance(deploy, dict) or set(deploy) - {"resources"}:
        errors.append(f"{path}.deploy: only deploy.resources is supported (no replicas or restart_policy)")
        return
    resources = deploy.get("resources") or {}
    if not isinstance(resources, dict) or set(resources) - set(allowed):
        errors.append(f"{path}.deploy.resources: only limits and reservations are supported")
        return
    for section, keys in allowed.items():
        block = resources.get(section) or {}
        if not isinstance(block, dict):
            errors.append(f"{path}.deploy.resources.{section}: must be a mapping")
            continue
        for key in set(block) - keys:
            errors.append(f"{path}.deploy.resources.{section}.{key}: not supported "
                          f"(allowed: {', '.join(sorted(keys))})")
        if "memory" in block and not MEMORY_RE.match(str(block["memory"])):
            errors.append(f"{path}.deploy.resources.{section}.memory: '{block['memory']}' is not a valid size (e.g. 512M, 2G)")
        if "cpus" in block:
            try:
                if float(block["cpus"]) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{path}.deploy.resources.{section}.cpus: must be a positive number")


def published_ports(data):
    ports = []
    for name, svc in (data.get("services") or {}).items():
        for port in svc.get("ports") or []:
            match = PORT_RE.match(port)
            ports.append({"service": name, "host_port": int(match.group(1)),
                          "container_port": int(match.group(2)), "protocol": match.group(4) or "tcp"})
    return ports


# deployment input name -> operation input name
_UPDATABLE_INPUTS = {"compose_yaml": "compose_yaml", "compose_environment": "compose_environment",
                     "registry_login_enabled": "registry_login_enabled", "registry_url": "registry_url",
                     "registry_credentials_secret": "registry_auth_ref"}


def _current_update():
    """The deployment-update record driving this execution, or None."""
    if ctx.workflow_id != "update":
        return None
    try:
        from dell import manager
        client = manager.get_rest_client()
        for update in client.deployment_updates.list(deployment_id=ctx.deployment.id):
            if update.get("execution_id") == ctx.execution_id:
                return update
    except Exception as err:
        ctx.logger.info(f"Could not read the deployment update record ({err}); using operation inputs")
    return None


def _pending_update_inputs():
    """New inputs of the deployment update driving this execution, if any.

    During a deployment update *preview* (dry run) operation inputs still
    resolve against the old deployment inputs, so check_drift would never
    see the change. The update record carries the new values.
    """
    new = (_current_update() or {}).get("new_inputs") or {}
    return {_UPDATABLE_INPUTS[k]: v for k, v in new.items() if k in _UPDATABLE_INPUTS}


def _desired():
    pending = _pending_update_inputs()

    def get(name, default):
        value = pending.get(name)
        return _input(name, default) if value is None else value

    text = get("compose_yaml", "")
    env = get("compose_environment", {})
    registry = {"enabled": get("registry_login_enabled", False),
                "url": get("registry_url", ""),
                "secret": get("registry_auth_ref", "")}
    return text, env, registry


def _applied_compose():
    """The substituted compose the plugin actually sent on its last create.

    The plugin stores it base64-encoded in runtime_properties.compose_config
    during precreate, on install and on every recreate.
    """
    encoded = ((ctx.instance.runtime_properties.get("compose_config") or {})
               .get("definition") or {}).get("compose")
    if not encoded:
        return None
    return base64.b64decode(encoded).decode()


def _fail(errors):
    raise NonRecoverableError(
        f"Compose definition is invalid or not supported on NativeEdge ({len(errors)} problem(s)):\n  - "
        + "\n  - ".join(errors))


def _drift_payload(resource_id, before, after, extra=None):
    diff_lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                           "applied", "desired", lineterm=""))
    diff = "\n".join(diff_lines + (extra or []))
    return {
        "resource_id": resource_id,
        "diff_count": sum(1 for l in diff_lines if l[:1] in "+-" and l[:3] not in ("+++", "---")) + len(extra or []),
        "diff": diff,
        "state_drift": None,
        "time": datetime.now().isoformat(timespec="microseconds"),
    }


def do_validate():
    text, env, registry = _desired()
    errors, warnings, data, substituted = validate(text, env, registry)
    for warning in warnings:
        ctx.logger.warning(warning)
    if errors:
        _fail(errors)
    rp = ctx.instance.runtime_properties
    rp["services"] = sorted(data["services"])
    rp["published_ports"] = published_ports(data)
    rp["desired_compose_sha256"] = sha256(substituted)
    rp["validated_compose"] = text
    rp["validated_substituted"] = substituted
    ctx.instance.update()
    ctx.logger.info(f"Compose definition valid: services={rp['services']} ports={rp['published_ports']}")


def _previous_substituted():
    """The substituted compose compose_definition last validated (for the drift diff).

    Instances validated before 1.0.6 only stored the raw text, so fall back to
    the update record's old inputs, then to the raw text.
    """
    rp = ctx.instance.runtime_properties
    if rp.get("validated_substituted") is not None:
        return rp["validated_substituted"]
    old = (_current_update() or {}).get("old_inputs") or {}
    if "compose_yaml" in old:
        env = old.get("compose_environment")
        return envsubst(old["compose_yaml"], env if isinstance(env, dict) else {})
    return rp.get("validated_compose", "")


def do_check_drift_def():
    text, env, _ = _desired()
    substituted = envsubst(text, env if isinstance(env, dict) else {})
    rp = ctx.instance.runtime_properties
    if sha256(substituted) == rp.get("desired_compose_sha256"):
        ctx.logger.info("compose_definition: no drift")
        ctx.returns(None)
        return
    ctx.logger.info("compose_definition: desired definition changed")
    ctx.returns(_drift_payload(ctx.instance.id, _previous_substituted(), substituted))


def _live_containers():
    """Container list from the Compute Service, or None if unavailable to a script."""
    import requests
    deployment_id = ctx.instance.runtime_properties.get("deployment_id")
    try:
        token = ctx.edge_estate_token
        initiator = ctx.edge_estate_initiator_token
    except Exception as err:  # attribute not exposed through the script ctx proxy
        ctx.logger.info(f"Container-state drift unavailable (no edge estate token in script ctx: {err})")
        return None
    if not token or not deployment_id:
        ctx.logger.info("Container-state drift unavailable (no token or compose deployment id)")
        return None
    host = os.getenv("EO_URL", "internal-ingress-gateway.istio-system.svc.cluster.local")
    url = f"http://{host}/compute/api/v2/containers?search=deployment_id:{deployment_id}"
    resp = requests.get(url, headers={"x-edge-estate-auth": token, "x-edge-estate-initiator": initiator}, timeout=30)
    if not resp.ok:
        ctx.logger.warning(f"Container-state drift unavailable (HTTP {resp.status_code} from Compute Service)")
        return None
    current = {}
    for container in resp.json().get("results") or []:
        extra = container.get("extra") or {}
        if isinstance(extra.get("data"), dict):
            container = {**container, **extra["data"]}
        current[container.get("containerName")] = container
    return current


def _container_state(info):
    for key in ("state", "status", "containerState"):
        if isinstance(info, dict) and info.get(key) is not None:
            return str(info.get(key))
    return None


def do_check_drift_compose():
    text, env, registry = _desired()
    rp = ctx.instance.runtime_properties
    errors, _, _, substituted = validate(text, env, registry)
    applied = _applied_compose()
    lines, before, after = [], applied or "", substituted

    if applied is not None and sha256(substituted) != sha256(applied):
        if errors:
            ctx.logger.warning("nativeedge_compose: desired definition changed but is INVALID; not reporting "
                               "drift so the running stack is left untouched (compose_definition update will fail)")
        else:
            lines.append("# definition changed")
    else:
        before = after = ""

    current = _live_containers()
    expected = rp.get("expected_containers") or {}
    if current is not None:
        mode = "definition + container-state"
        for cname in sorted(set(expected) | set(current)):
            if cname not in current:
                lines.append(f"# container missing: {cname}")
            elif cname not in expected:
                lines.append(f"# unexpected container: {cname}")
            elif _container_state(current[cname]) != _container_state(expected[cname]):
                lines.append(f"# container {cname} state {_container_state(expected[cname])} -> "
                             f"{_container_state(current[cname])}")
    else:
        mode = "definition only"
    ctx.logger.info(f"nativeedge_compose drift mode: {mode}")

    if not lines:
        ctx.logger.info("nativeedge_compose: no drift")
        ctx.returns(None)
        return
    ctx.logger.info("nativeedge_compose drift: " + "; ".join(lines))
    ctx.returns(_drift_payload(ctx.instance.id, before, after, lines))


def do_recreate_gate():
    text, env, registry = _desired()
    errors, _, _, _ = validate(text, env, registry)
    if errors:
        _fail(errors)
    raise NonRecoverableError(
        "EXPECTED: the NativeEdge Compute Service has no in-place compose update, so this update "
        "intentionally fails and the update workflow recreates the compose with the new definition "
        "(delete + create). The stack is briefly unavailable while it is recreated.")


def do_postupdate():
    rp = ctx.instance.runtime_properties
    summary = {k: rp.get(k) for k in ("services", "published_ports", "desired_compose_sha256")
               if rp.get(k) is not None}
    applied = _applied_compose()
    if applied is not None:
        summary["applied_compose_sha256"] = sha256(applied)
    ctx.logger.info(f"postupdate {ctx.node.id}: {json.dumps(summary)}")


def do_release():
    # compose_definition has no external side effects; nothing to revert
    ctx.logger.info("compose_definition: nothing to clean up")


ACTIONS = {
    "release": do_release,
    "validate": do_validate,
    "check_drift_def": do_check_drift_def,
    "check_drift_compose": do_check_drift_compose,
    "recreate_gate": do_recreate_gate,
    "postupdate": do_postupdate,
}

# Runs unconditionally (the script runner may not execute us as __main__);
# offline tests set COMPOSE_OPS_NO_MAIN to import the helpers only.
if not os.getenv("COMPOSE_OPS_NO_MAIN"):
    action = _input("action")
    if action not in ACTIONS:
        raise NonRecoverableError(f"compose_ops: unknown action '{action}'")
    ACTIONS[action]()
