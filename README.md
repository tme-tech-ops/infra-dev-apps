# Multi-purpose Example Blueprint

This blueprint provides five example deployments for the purpose of NativeEdge blueprint demonstration and training. When uploading the blueprint, the user may choose from five deployment options. Three deployments leverage an Ubuntu 22.04 cloudinit VM on a NativeEdge Endpoint, one deploys bare-metal containers directly on the NativeEdge Endpoint, and one deploys to a remote 3rd-party host.

Deployment options:
1. `simple_vm_example_for_NED.yaml` - Deploys a basic Ubuntu VM on a NativeEdge Endpoint. Provides VM login details on completion.
2. `mqtt_nodered_example_for_NED.yaml` - Deploys a VM, installs Docker, and runs Node-Red and MQTT containers with a simple Node-Red flow configured.
3. `nginx_app_example_for_NED.yaml` - Deploys NGINX with SSL and basic authentication on an existing `simple_vm` deployment, providing a web page and simple artifact repository.
4. `container_based_example_for_NED.yaml` - Deploys Node-Red, InfluxDB, and Grafana containers directly on a NativeEdge Endpoint using NativeEdgeCompose.
5. `remote_host_example.yaml` - Uses the Fabric plugin to install NGINX with SSL and basic authentication on a remote host outside of NativeEdge.

Key features:
- Minimal user input to showcase the simplicity of blueprint deployment
- Multi-purpose blueprint provides versatility for demonstration and training
- Supports DHCP and static IP assignment
- Supports Bridge and NAT type networks, with optional port forward rules
- Supports up to two NIC definitions
- Supports optional device passthrough for GPU, video, serial, USB, and PCIe
- Auto-generates SSH keys that are re-usable for user authentication
- Supports standard username/password authentication for VM and NGINX server
- Supports bare-metal container deployment
- Supports deploying to a remote 3rd-party host

## Deployment Prerequisites

*For VM based deployments (simple_vm, mqtt_nodered, nginx_app)*
1. An Orchestrator running on version 1.0.0.0 or higher
2. A NativeEdge Endpoint onboarded
3. A bridged or NAT virtual network segment on the NativeEdge Endpoint
4. An Ubuntu Server LTS 22.04 cloud image (default from ubuntu.com)
5. Internet access for the VM to install Docker Engine
6. Internet access to pull Node-Red and MQTT containers, or access to the containers through a local registry
7. Internet access to install NGINX and apache2-utils via apt-get package manager

*For bare-metal container deployments (container_based)*
1. A NativeEdge Orchestrator running on version 1.0.0.0 or higher
2. A NativeEdge Endpoint onboarded
3. Internet access to pull Node-Red, Grafana, and InfluxDB containers, or access to the containers through a local registry

*For remote host deployments (remote_host)*
1. A NativeEdge Orchestrator running on version 1.0.0.0 or higher
2. Internet access to install NGINX packages
3. A remote host running Ubuntu 22.04 or higher with a public SSH key in the authorized_keys list (`~/.ssh/authorized_keys`)
4. A secret created in the NativeEdge Orchestrator for both the matching private key and sudo password of the remote host
5. The user must be root, or be a sudo user configured as `ALL=(ALL) NOPASSWD:ALL`

### Dell Automation Platform Secrets

Dell Automation Platform Secrets are created from the Orchestrator UI from the **Administration > Security > Secrets** tab.

1. *Required for simple_vm, mqtt_nodered* Create a Binary Configuration type secret that points to an Ubuntu Cloud Image. You can point directly to cloud-images.ubuntu.com if the internet is accessible from the Orchestrator. Example values:

```
Key: os-image-secret
Name: os-image-secret
Description: URL and credentials for downloading the OS image for Virtual Machine Creation
Type: Binary Configuration
Value: As Form
Binary Image Url: https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
Binary Image Access User: # Leave blank for public Ubuntu cloud image, or provide username for private artifact server
Binary Image Access Token: # Leave blank for public Ubuntu cloud image, or provide password for private artifact server
Binary Image Version: 22.04 # Logical version for reference
```

2. *Required for simple_vm, mqtt_nodered* Create a Password type secret containing the plain-text password for VM user authentication. The plain-text password is automatically hashed during blueprint creation to follow cloud-init configuration standards.

```
Key: vm_password
Name: vm_password
Description: Plain-text password for VM user authentication
Type: Password
Value: As Form
Password Schema: YourSecurePassword
```

3. *Only needed for mqtt_nodered* A Docker Configuration type secret containing the username and password for Docker to log in to the registry. The default registry points to docker.io unless a private registry is specified.

```
Key: registry_credentials
Name: registry_credentials
Description: Registry username and password
Type: Docker Configuration
Value: As Form
Username: YourUsername
Password: YourSecurePassword
```

4. *Only needed for remote_host* Create an SSH private key type secret from a generated SSH key pair, and a Password type secret for the remote host's root/sudo password. If an SSH key pair does not already exist, it is easiest to create from the remote host itself:

```bash
ssh-keygen -m PEM -t RSA
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/id_rsa
```

Copy the output of `cat ~/.ssh/id_rsa` — this is your private key.

Create an SSH private key type secret:
```
Key: remote_host_private_key
Name: remote_host_private_key
Description: Private key for remote host SSH authentication
Type: SSH private key
Value: As Form
SSH Private Key Schema: # Output from the id_rsa or private key file
```

Create a Password type secret:
```
Key: remote_host_sudo_password
Name: remote_host_sudo_password
Description: Sudo password for remote host
Type: Password
Value: As Form
Password Schema: YourSecurePassword
```

## Getting Started

1. Upload the blueprint directory to the Orchestrator from **Infrastructure > Blueprints** and select the corresponding YAML file for the desired deployment (`simple_vm_example_for_NED.yaml`, `nginx_app_example_for_NED.yaml`, `mqtt_nodered_example_for_NED.yaml`, `container_based_example_for_NED.yaml`, or `remote_host_example.yaml`).
2. Verify the Endpoint has a virtual network configured (bridged or NAT). *Not applicable for remote_host or container_based.*
3. From the blueprint inventory, deploy by selecting the blueprint from the list and clicking **Deploy**.
4. Select the Endpoint deployment target. *Not applicable for remote_host.*
5. Fill out the deployment modal with the required inputs, modifying the defaults and optional inputs if needed.

Once deployed, monitor the status by clicking on the deployment name and selecting the **Logs** tab. The user may also check the Endpoint Details > **Virtual Machines** or **Containers** tab to see the resources being deployed. When complete, access the virtual machine and application using the information from the **Inputs/Capabilities** tab on the deployment details page.

## Capabilities

The following capabilities are provided on a successful deployment:

**simple_vm deployment:**
- Service Tag
- VM hostname
- VM IP address
- VM name
- VM SSH private key secret name
- VM username

**mqtt_nodered deployment:**
- Service Tag
- VM hostname
- VM IP address
- VM name
- VM SSH private key secret name
- VM username
- MQTT endpoint (`tcp://<vm-ip>:1883`)
- Node-Red URL (`http://<vm-ip>:1880`)

**nginx_app deployment:**
- NGINX URL (`https://<vm-ip>:<port>`)
- NGINX username
- NGINX password

**container_based deployment:**
- Node-Red URL (`http://<endpoint-ip>:1880`)
- InfluxDB URL (`http://<endpoint-ip>:8086`)
- Grafana URL (`http://<endpoint-ip>:3000`)

**remote_host deployment:**
- NGINX URL (`https://<remote-host>:443`)

## Customization

This blueprint is designed with customization in mind and may be tailored to specific use cases, such as VM device passthrough or modifying container deployments. Inspect the following directories for specific customizations:

### `vm` directory

- `definitions.yaml` — Contains logic for configuring SSH keys, creating the VM, creating a cloud-init configuration, and establishing a proxy connection for VM communication over the endpoint internal network.
- `inputs.yaml` — Contains hardware passthrough inputs for USB, serial, video, GPU, and generic PCIe devices, as well as all other VM inputs. To leverage passthrough inputs in a deployment, change the `hidden:` value to `false`. When set to `false`, these inputs will be visible during blueprint deployment.

### `mqtt_nodered` directory

- `definitions.yaml` — Contains logic for running Ansible playbooks from the `playbooks/` directory. Modify to add additional node tasks based on the use case.
- The default playbooks install Docker Engine on the Virtual Machine, then run Docker Compose for MQTT and Node-Red.

### `nginx_app` directory

- `definitions.yaml` — Contains logic for running commands using the Fabric plugin. Modify to add additional commands or node tasks based on the use case.
- The commands clone a public git repository and run the install script with the specified environment variables, which installs a basic NGINX web app for serving static files using SSL.

### `container_based` directory

- `definitions.yaml` — Contains logic for running the NativeEdgeCompose node for deploying containers directly on the NativeEdge Endpoint.
- The `compose/container_compose.yaml` file may be modified to use different container images or add additional services based on the use case.

### `remotehost` directory

- `definitions.yaml` — Leverages the same Fabric plugin and commands as `nginx_app` but disables the proxy connection, allowing the blueprint to run against any supported 3rd-party host.
- The inputs and definitions may be modified to provide different results.

## Advanced Considerations

When using NAT Port Forward Rules, the following is required:

- NAT type Virtual Network Segment must be selected
- `host_ip` must equal the Host Network IP from the interface where the NAT is created
- `host_port` is the port to connect on from the `host_ip`
- `protocol` must equal `TCP` or `UDP`
- `service_type` must be `HTTP`, `SSH`, or `CUSTOM`
- `vm_ip` may be left blank if DHCP is used
- `vm_port` is the local port of the application to forward
