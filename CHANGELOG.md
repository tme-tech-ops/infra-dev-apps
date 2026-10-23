# Changelog for infra-dev-apps

All notable changes to this blueprint are recorded here.

## 4.0.0 - unreleased

Breaking: entry file names and catalog labels changed. Re-upload the
blueprint and select the new entry file. Existing deployments are not
affected.

- Changed: DDPC rebrand. The collection now targets Dell Distributed Private
  Cloud (DDPC), orchestrated by the Dell Automation Platform (DAP). Entry
  files are renamed (`git mv`, history kept):
  - `simple_vm_example_for_NED.yaml` -> `simple_vm_example_for_DDPC.yaml`
  - `mqtt_nodered_example_for_NED.yaml` -> `mqtt_nodered_example_for_DDPC.yaml`
  - `nginx_app_example_for_NED.yaml` -> `nginx_app_example_for_DDPC.yaml`
  - `container_based_example_for_NED.yaml` -> `container_based_example_for_DDPC.yaml`
  - `compose_app_example_for_NED.yaml` -> `compose_app_example_for_DDPC.yaml`
  - `remote_host_example.yaml` is unchanged (not DDPC-specific).
- Changed: labels on all six entry files. `target_environment` is renamed
  to `env` (`nativeedge` -> `ddpc`; remote_host keeps `remote`), `vendor` is
  removed, and `solution` is `tme-tech-ops` everywhere (was `EXAMPLE-*` /
  `GENERIC-COMPOSE`). `blueprint_labels.env: ned` -> `ddpc`.
  `csys-obj-type` and `version` keep their roles. The env label change does
  not affect catalog visibility, the Deploy On picker or install (verified on
  DDPC 4.3.0.0).
- Changed: descriptions, input group labels, capability descriptions,
  comments, README and compose_app validation/log messages say DDPC / DAP
  instead of NativeEdge. Edge-plugin identifiers (`NativeEdgeVM`,
  `NativeEdgeCompose`, `RegistryLogin`, `BinaryImage`, `nativeedge_plugin.tasks.*`,
  the `nativeedge_compose` node name, the `nativeedge` script context module)
  are plugin API names and are unchanged.
- Changed: blueprint version labels: simple_vm, mqtt_nodered, nginx_app,
  container_based, remote_host 3.2.0 -> 4.0.0; compose_app 1.0.6 -> 1.1.0.
- Changed: `CHANGELOG.txt` -> `CHANGELOG.md` (dap-bpa BS-009). Earlier
  entries below are kept as written.
- Changed (breaking, nginx_app + remote_host): the NGINX basic-auth
  username and password now come from a Basic Auth Credentials secret.
  The `nginx_htuser` / `nginx_htpass` inputs are replaced by
  `nginx_credentials_secret`. nginx_app no longer returns the
  `nginx_username` / `nginx_password` capabilities; both blueprints expose
  `nginx_credentials_secret` (the secret name) instead.
- Changed (mqtt_nodered): the registry login moved to its own `docker_login`
  node, created only when Use Docker Authentication is enabled. The username
  and password are read straight from the Docker Configuration secret, and
  `docker login` gets the password on stdin with `no_log`, so it no longer
  shows in the process list or the Ansible log. The hidden
  `registry_username` / `registry_password` inputs are removed.
- Changed: plugin imports moved from the component `definitions.yaml` files
  into each entry file (IM-002). Minimums raised to the DDPC 4.3.0.0 set:
  edge-plugin 3.3.33.0, utilities-plugin 3.2.3.0, fabric-plugin 3.4.3.0,
  ansible-plugin 4.1.9.0 (now with a `<5.0.0.0` upper bound). nginx_app
  imports only fabric-plugin, the only plugin it uses.
- Changed: inputs brought up to the compliant shape: every input sets
  `hidden` and `allow_update`, every constraint has an `error_message`,
  booleans are constrained to true/false, list inputs have an `item_type`,
  and integers have ranges (ports 1-65535, certificate days 1-3650, Ansible
  debug 0-3 and timeout 60-86400 s, NGINX debug 0/1). container_based
  inputs gained descriptions, constraints and correct input groups.
  remote_host `ssh_private_key` is constrained to the SSH private key schema.
- Changed: the hidden `binary_image_access_token` input is removed; the
  BinaryImage node reads the path into the OS image secret directly.
- Changed (container_based): the compose-file loader moved from inline code
  to `container_based/scripts/prepare_compose_yaml.py` (ND-005). It fails
  clearly if the file is missing.
- Fixed (container_based): the Node-RED Image input had no effect (the
  compose file read `${NODE_RED_URL}`, the blueprint passed `NODERED_URL`).
- Fixed (container_based): the Grafana input group was labelled "Device
  Passthrough".
- Fixed (simple_vm / mqtt_nodered): `os_image_secret` referenced a
  non-existent input group (`artifacts` instead of `artifact`).
- Changed (nginx_app / remote_host): page titles and credentials are
  single-quoted in the install environment. Fabric exports environment
  values unquoted, so values with spaces or shell metacharacters could be
  cut off.
- Fixed (remote_host): the `nginx_url` capability ignored Nginx Port and
  always used 443.

## 3.3.0 - 2026-10-21
- Added: compose_app_example_for_NED.yaml + compose_app/ (blueprint
  revision 1.0.6), a generic NativeEdgeCompose deployment split from
  container_based. Free-form compose definition input, validated against
  the compose features NativeEdge supports (all problems reported as
  errors before anything reaches the endpoint); ${VAR} substitution from
  Compose Environment; optional registry login via a basic_auth_credentials
  secret (input group, conditional inputs, TLS verify toggle).
- Added: Day-2 support for compose_app. A definition or used-variable
  change recreates the stack (named-volume data is kept); invalid changes
  fail the update without touching the running stack; drift detection
  covers the definition and live container state, and a no-change update
  heals container drift. Validated on EdgeOS 4.3.0.0 / edge-plugin 3.3.33.0.
- Fixed (compose_app 1.0.5): the UI Next button stayed disabled with default
  inputs. The compose_yaml pattern no longer uses the Python-only (?s) flag,
  and compose_environment is required: false.
- Changed (compose_app 1.0.6): Compose Definition description and README
  now document that only named-volume data survives a recreate.
- Fixed (compose_app 1.0.6): the compose_definition drift view was empty for
  variable-only changes. It now diffs the substituted compose (previous vs
  desired), like nativeedge_compose. (compose_app/scripts/compose_ops.py)
- Known issue: private registry pulls fail with `unauthorized` even after a
  successful registry login (platform issue).
  Anonymous/public pulls work.
- Changelog kept as CHANGELOG.txt: a CHANGELOG.yaml at the blueprint root
  is offered as an entry point by the DAP blueprint upload selector.

## 3.2.1 - 2026-06-09
- Fixed: VM password hashing now uses bcrypt instead of the stdlib `crypt`
  module. The DAP deployment agent runs Python 3.14, where `crypt` was
  removed; `import crypt` failed at runtime and stalled VM-based deploys at
  the prepare_config start operation. cloud-init accepts the bcrypt ($2b$)
  hash in the user `passwd` field. Mirrors the edge-cloudinit-linux fix.
  (vm/scripts/prepare_passwd.py)
- Fixed: SyntaxError in get_target_id.py (missing commas in the
  connection_proxy_settings dict literals, lines 74 and 81), introduced when
  the enable_socks5 proxy setting was added. This failed the vm_info node and
  blocked every VM-based deploy at install time. (vm/scripts/get_target_id.py)
- Changed: vm_password input description clarified (plain-text secret,
  hashed with bcrypt at deploy time). (vm/inputs.yaml)
- Added: this CHANGELOG.

## 3.2.0
- Baseline version prior to changelog tracking.
  Five example deployments: simple_vm, mqtt_nodered, nginx_app,
  container_based, remote_host.
