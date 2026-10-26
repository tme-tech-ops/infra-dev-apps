# Changelog for infra-dev-apps

All notable changes to this blueprint are recorded here.

## 4.3.1 - unreleased

compose_app review (Day-2 rules from 4.1–4.3; regression on the live
platform, see the PR).

- Fixed (compose_app): an update with an invalid definition could delete the
  running stack. If a container had also stopped (container-state drift),
  `nativeedge_compose` still reported drift; its update failed on the invalid
  definition and, with "Run automatic reinstall" checked, the orchestrator
  deleted the stack and could not create it again. The drift check now
  reports nothing while the desired definition is invalid, so only
  `compose_definition`'s update fails and the stack keeps running.
- Changed (compose_app): version label 1.1.0 -> 4.3.1, in line with the repo
  version (the catalog revision was already 4.0.0). No functional change.
- Docs (compose_app): a failed update still saves the new input values; fix
  them in the next update. If a stack was removed by a failed update, run
  Install on the deployment to recreate it.

## 4.3.0 - 2026-10-26

- Added (it_toolkit_compose): deployment updates. Site Name, Alert Topic, the
  health-check targets, Check Interval, the four ports and Image Registry can
  now be changed. `nativeedge_compose` has a drift check
  (`site_it_toolkit/scripts/toolkit_ops.py`): the compose with the desired
  settings vs the one the plugin last sent, plus container state. Its update
  fails on purpose so the workflow recreates the stack (check "Run automatic
  reinstall"); the named volumes (status history, alert cache) are kept.
  `prepare_compose_yaml` re-reads the compose file when a new blueprint
  revision changes it. Same design as compose_app. The registry login inputs
  stay fixed. See "Updating an it_toolkit_compose deployment" in the README.

## 4.2.0 - 2026-10-26

iot_factory (all three entries) gets deployment updates. simple_vm and
iot_factory_vm get a VM drift check.

- Added (iot_factory): deployment updates. Telemetry Interval, Auto Chaos
  Mode, Grafana Anonymous Viewer, the six service ports and the Ansible
  settings can now be changed. Accept Joins / Join A Hub Factory stay set at
  install: a deployment update doesn't add or remove their node instances.
  `deploy_stack` has a drift check (`iot_factory/scripts/stack_drift.py`)
  that compares the desired settings with the ones its last successful run
  applied, and its update runs preflight (a changed port must be free), the
  deploy and verify_demo in one run (`iot_factory/playbooks/update_stack.yaml`).
  The other Ansible nodes report no drift (`iot_factory/scripts/no_drift.py`),
  so they are no longer reinstalled. The first update after upgrading re-runs
  deploy_stack once. See "Updating an iot_factory deployment" in the README.
- Fixed (iot_factory on DDPC, VM and layered): Ansible runs other than the
  install could not reach the VM through the Endpoint proxy (UNREACHABLE,
  "Could not resolve hostname"). The run's inventory was built from the proxy
  address of the previous run, which the plugin released when it looked up a
  new one. Each node now resolves the address just before its run
  (`iot_factory/scripts/proxy_endpoint.py`: precreate, preupdate, and
  prestop on the layered entry) and the plugin's `inventory_proxy_settings`
  is no longer used.
- Added (simple_vm, iot_factory_vm): a VM drift check
  (`vm/scripts/vm_check_drift.py`) replaces the edge-plugin's, which always
  reported drift. An update that doesn't change the VM (including any
  iot_factory-only update) no longer sends it a no-op update, which the
  Endpoint sometimes never completed (the 4.1.0 known issue).
- Changed (iot_factory): preflight treats only the ports the deployed stack
  publishes (recorded in `/opt/iot-factory/applied.json`) as its own.
- Fixed (simple_vm, iot_factory_vm): ticking "Add Second NIC" in the update
  form of a deployment created without one showed "Static IP and CIDR prefix
  for second NIC" with an "invalid character" error, and Next stayed blocked
  even after unticking it. The input is stored as null and the form validated
  that value. The static IP and gateway patterns now also accept blank, "null"
  and "None", and `prepare_netplan_config.py` checks for a real value when it
  is needed.
- Fixed (simple_vm, iot_factory_vm): with DHCP off, the install required a
  gateway even when "Use Gateway" was unchecked.

## 4.1.0 - 2026-10-26

simple_vm and iot_factory on a new DDPC VM (the `vm/` component).

- Added: deployment updates for the VM. vCPUs, memory, OS disk size (grow
  only), both NIC segments, adding or removing NIC 2, NAT port-forward rules
  and USB passthrough can now be changed by a deployment update. Every applied
  change reboots the VM. See "Updating a simple_vm deployment" in the README
  for the tested results and the update options to use.
- Added: `additional_disks` input (data type `additional_disk`) for empty data
  disks. Disks can be added, grown or removed by an update; removing one
  deletes it.
- Added: NIC names are pinned to MAC addresses at first boot (`data0`,
  `data1`, `mgmt0`) by `vm/templates/pin_nic_names.sh`, and NICs added later
  get DHCP. Before this, adding a NIC renamed the management NIC and cut off
  the Endpoint proxy.
- Added: an `update_postapply` check (`vm/scripts/vm_postupdate.py`) that fails the
  update if the VM record doesn't match the vCPUs, memory, disks or NIC
  segments that were sent.
- Fixed: a NIC segment or NAT rule change was not applied by an update. The
  NIC list is now built from the inputs in the VM's own properties (and sends
  `model_type: VIRTIO`); `prepare_network_settings.py` is removed.
- Fixed: the `vm_ip` capability went stale after an update that changed the
  VM's address. `vm_info` now writes a top-level `vm_public_ip` runtime
  property (nested keys aren't saved by update operations).
- Changed: `boot_order` (hidden) accepts only `hd`, `cdrom` and `network`.
- Known issue: an update that changes nothing on the VM occasionally never
  completes on the Endpoint (`update_apply` polls for up to an hour). Cancel it;
  the VM is not affected.
- Upgrade note: updating a 4.0.x deployment to this revision reboots the VM
  once. VMs created before 4.1.0 are not pinned: adding NIC 2 to them cuts
  off the management connection (remove it again to recover).

## 4.0.1 - 2026-10-26

- Fixed (simple_vm, iot_factory_vm): the deployment update form could not be
  completed. With no second NIC, "Static IP and CIDR prefix for second NIC"
  was shown, filled with a stored empty value, and failed validation while
  greyed out. `static_ip2` and `use_dns2` are now also `only_with:
  add_second_nic`.
- Changed (simple_vm, iot_factory_vm): `os_image_secret` and the hidden
  `disk_controller` can no longer be changed by a deployment update. The
  edge-plugin never sends the image in a VM update, and the boot-disk
  controller of a running VM can't change.
- Changed (simple_vm, iot_factory_vm): `vnic_0_segment_name` and
  `vnic_1_segment_name` can no longer be changed by a deployment update. The
  update completed but the VM stayed on its old segment, because the NIC list
  is computed once at install.
- Changed (iot_factory, all three entries): `ansible_debug_level`,
  `ansible_timeout` and `ansible_log_stdout` can no longer be changed by a
  deployment update. Every Ansible node reads them and has no update
  operation yet, so a change would have reinstalled (torn down and redeployed)
  the stack.

## 4.0.0 - 2026-10-25

Breaking: entry file names and catalog labels changed. Re-upload the
blueprint and select the new entry file. Existing deployments are not
affected.

- Removed (breaking): consolidated to six entry points.
  - `mqtt_nodered_example_for_DDPC.yaml` (`mqtt_nodered/`): superseded by the
    IoT Smart Factory, which includes Mosquitto and Node-RED.
  - `nginx_app_example_for_DDPC.yaml` (`nginx_app/`): replaced as the layered
    example by `iot_factory_layered_for_DDPC.yaml`. It also depended on an
    external install-script repository.
  - `remote_host_example.yaml` (`remotehost/`): superseded by
    `iot_factory_remote_host_example.yaml`.
- Changed (breaking): `container_based_example_for_DDPC.yaml` is renamed to
  `it_toolkit_compose_for_DDPC.yaml`, and `container_based/` to
  `site_it_toolkit/`.
- Changed (breaking): `iot_factory/outputs.yaml` is renamed to
  `iot_factory/capabilities.yaml`.
- Changed (breaking): `container_based` now deploys the **Site IT Toolkit**
  instead of Node-RED / InfluxDB / Grafana: a Gatus status page that checks
  the site uplink, its TLS certificate, the DNS resolver, a named key service
  and the toolkit itself, ntfy push alerts (Gatus alerts after 3 failed
  checks and on recovery), an OpenSpeedTest LAN speed test and the IT-Tools
  toolbox. The whole stack is configured in
  `container_based/compose/site_it_toolkit.yaml` (replaces
  `container_compose.yaml`); the Gatus configuration is inline and rendered
  into a named volume by an `itk-config` service, because DDPC rejects bind
  mounts. `itk-config` also fills in the compose DNS server and the alerts
  service IP, because the scratch-based Gatus image gets no
  `/etc/resolv.conf` on DDPC. All images are pinned public images with resource limits. The
  per-container name/image inputs are replaced by site, health-check, port
  and image-registry inputs, and `container_based/outputs.yaml` is now
  `capabilities.yaml` (status page, alerts, speed test and toolbox URLs).
- Added (container_based): optional registry login (`registry_login_enabled`,
  `registry_url`, `registry_credentials_secret`, `registry_tls_verify`), the
  same `RegistryLogin` wiring as compose_app. On EdgeOS 4.3 the login reports
  success but pulls stay anonymous (known platform issue).
- Added: `iot_factory_remote_host_example.yaml` (`iot_factory/`), an IoT Smart
  Factory demo for any SSH-reachable Ubuntu 24.04 host. Ansible installs Docker
  CE from the official repo, then Mosquitto, Node-RED (line simulator, fault
  injection by button, MQTT or REST, alert rules), InfluxDB 2 and a provisioned
  Grafana dashboard. A preflight node refuses other OSes before changing
  anything. Uninstall reverts the host, including Docker when the blueprint
  installed it. Tested on Ubuntu 24.04 only.
- Added: `iot_factory_vm_for_DDPC.yaml` (`vm/` + `iot_factory/ddpc_vm/`), the
  IoT Smart Factory demo on a new Ubuntu 24.04 cloud-init VM that the
  deployment creates on a DDPC Endpoint. The same playbooks run through the
  Endpoint proxy (eo-proxy). Uninstall removes the VM.
- Added: `iot_factory_layered_for_DDPC.yaml` (`iot_factory/ddpc_layered/`), the
  IoT Smart Factory demo layered onto the VM of an existing simple_vm deployment
  (Ubuntu 24.04), which it reads with `get_environment_capability`. The same
  playbooks run through the Endpoint proxy (eo-proxy), so the VM doesn't need
  to be reachable from the orchestrator. Uninstall runs the teardown playbooks
  and leaves the VM. The remote-host inputs moved to
  `iot_factory/remote_host_inputs.yaml` so both entries share
  `iot_factory/inputs.yaml`.
- Added (iot_factory): second fault per machine with build-up behaviour
  (`hydraulic_leak`, cumulative `tool_wear` and `misgrip`), line cascades
  (STARVED), runtime chaos mode that runs alongside manual faults, scenarios,
  a Node-RED control room (`/control`: live line cards, fault buttons,
  terminal, live MQTT feed), MQTTX Web with a Mosquitto websocket listener,
  multi-factory joining over a Mosquitto bridge (`accept_joins` on the hub
  with a dedicated, ACL-limited bridge login; `join_hub` on the joiner), a reworked
  Grafana dashboard (how-to, fault build-up, factory network, data pipeline
  health, site/line selectors) and an InfluxDB Database Health dashboard.
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
