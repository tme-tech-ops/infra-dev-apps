# POC Example Blueprint

This blueprint provides three example deployments for the purpose of NativeEdge blueprint demonstration and training. When uploading the blueprint, the user may choose four different deployment options. Three deployments leverage an Ubuntu 22.04 cloudinit VM on a NativeEdge Endpoint, while the fourth deploys bare-metal containers on the NativeEdge Endpoint.

Deployment options:
1. mqtt_nodered_example_for_NED.yaml - Deploys a VM, installs docker and runs NodeRed and MQTT containers with a simple NodeRed flow deployed.
2. nginx_app_example_for_NED.yaml - Deploys on an existing simple_vm_example, NGINX with ssl and basic authentication, providing a web page and simple artifact repository.
3. simple_vm_example_for_NED.yaml - Only deploys a basic Ubuntu VM where the user may login.
4. container_based_example_for_NED.yaml - Deploys Node-Red, InfluxDB, and Grafana containers on a NativeEdge endpoint.
5. remote_host_example.yaml - Uses the Fabric plugin to install NGINX with ssl and basic authentication to a remote host, outside of NativeEdge.

Key features:
- Minimal user input to showcase the simplicity of blueprint deployment
- multi-use blueprint provides versatility for demonstration and training
- Supports DHCP and STATIC IP assignment
- Supports Bridge and NAT type networks, with optional port forward rules
- Supports up to two NIC definitions
- Supports optional devices passthrough for gpu, video, serial, usb, and pcie
- Auto-generates ssh keys that are re-usable for user authentication
- Supports standard username/password authentication for VM and NGINX server
- Supports bare-metal container deployment
- Supports deploying to a remote 3rd-party host

## Deployment Prerequisites

*For VM based deployments*
1. A Orchestrator running on version 1.0.0.0 or higher
2. A NativeEdge Endpoint onboarded
3. A bridged or NAT virtual network segment on the NativeEdge Endpoint
4. An Ubuntu Server LTS 22.04 cloudinit image, default from ubuntu.com
5. Internet access for the VM to install docker engine
6. Internet access to pull NodeRed, and MQTT containers, or access to the containers through a local registry
6. Internet access to install nginx and apache2-utils via apt-get package manager

*For Bare-metal container deployments*
1. A NativeEdge Orchestrator running on version 1.0.0.0 or higher
2. A NativeEdge Endpoint onboarded
3. Internet access to pull Node-Red, Grafana, and InfluxDB containers, or access to the containers through a local registry

*Fore Remote host deployments"
1. A NativeEdge Orchestrator running on version 1.0.0.0 or higher
3. Internet access to install NGINX packages
3. A remote host running Ubuntu 22.04 or higher with a public ssh key in the authorized_keys list (~.ssh/authorized_keys)
4. A secret created in NativeEdge Orchestrator for both the matching private key and sudo password of the remote host
5. The user must be root, or be a sudo user configured as `ALL=(ALL) NOPASSWD:ALL`

### Dell Automation Platform Secrets:

Dell Automation Platform Secrets are created from the Orchestrator UI from the Administration > Security > Secrets tab. 

1. Create a Binary Configuration type secret that points to an Ubuntu Cloud Image. You can point directly to cloud-images.ubuntu.com if the internet is accessible from the Orchestrator. Here are some example values for filling out the Create Secret Form

```
Key: poc-os-image-secret
Name: poc-os-image-secret
Description: URL and credentials for downloading the OS image for Virtual Machine Creation
Type: Binary Configuration
Value: As Form
Binary Image Url: https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
Binary Image Access User: # Leave blank for public ubuntu cloud image, or provide user name for private artifact server
Binary Image Access Token: # Leave blank for public ubuntu cloud image, or provide password for private artifact server
Binary Image Version: 22.04 # Logical version for reference
```

2. Create a Password type secret. This secret should contain the plain-text password to be used for VM user authentication. The plain-text password is automatically hashed during blueprint creation in order to follow the cloud-init configuration standards.

```
Key: vm_password
Name: vm_password
Description: Plain-text password for vm user authentication
Type: Password
Value: As Form
Password Schema: YourSecurePassword
```

3. *Only needed for mqtt_nodered deployment* A Docker Configuration type secret containning the username and password for docker to login to the registry. The default registry points to docker.io unless a private registry is specified.
```
Key: registry_credentials
Name: registry_credentials
Description: Registry username and password
Type: Docker Configuration
Value: As Form
Username: YourUsername
Password: YourSecurePassword
```

4. *Ony needed for remote_host blueprint* Create SSH private key type secret from a generated ssh key pair and a Password type secret of the remote hosts root/sudo password. If an SSH key pair is not already created, this is easiest to create from the remote host its self using:
```bash
ssh-keygen -m PEM -t RSA
cat ~.ssh/id_rsa.pub > ~.ssh/authorized_keys
cat ~.ssh/id_rsa
```
Copy the output of `cat ~.ssh/id_rsa`. This is your private key.
Create a SSH private key type secret:
```
Key: remote_host_private_key
Name: remote_host_private_key
Description: Private key for my remote host ssh authentication
Type: SSH private key
Value: As Form
SSH Private Key Schema: #Output from the id_rda or private key file
```

Create a Password type secret:
```
Key: vm_password
Name: vm_password
Description: Plain-text password for vm user authentication
Type: Password
Value: As Form
Password Schema: YourSecurePassword
```

## Getting started

1. Upload the POC_Example_Blueprint.zip to the Orchestrator from Infrastructure > Blueprints and select the coresponding yaml for simple_vm, nginx_app, mqtt_nodered, container_based, or remote_host.
2. Verify the Endpoint has a virtual network configured either bridged or NAT *not applicable for remote_host or mfg_container*
3. From the blueprint inventory, deploy by selecting the blueprint from the list and clicking Deploy.
4. Select the Endpoint deployment target. *not applicable for remote_host*
5. Fill out the deployment modal with the required inputs, modifying the default & optional inputs if needed. \

Once deployed, monitor the status of the deployment by clicking on the deployment name clicking on the Logs tab. The user may also check the the Endpont Details > Virtual Machine | Containers tab to see the resources being deployed. When the deployment is complete, access the virtual machine and application using the information from the Inputs/Capabilities tab on the deployment details page.
    
## Capabilites

The following capabilities/outputs are provided on a successful deployment:

VM deployment:
- Service Tag
- VM hostname
- VM ip address
- VM name
- VM ssh private key secret name
- VM username

NodeRed and MQTT only deployment:
- Service Tag
- VM hostname
- VM ip address
- VM name
- VM ssh private key secret name
- VM username
- MQTT endpoint
- NodeRed URL

NGINX deployment:
- nginx URL

MFG Container only deployment:
- Node-Red URL
- InfluxDB URL
- Grafana URL

Remote host deployment
- NGINX URL

## Customization

This blueprint is designed with customization in mind and may be tailored to specific POC use cases, such as VM device passthrough or modifying the container deployments. Inspect the following for specific customizations

### 'vm' directory

- definitions.yaml Contains logic for configuring ssh keys, creating the VM, creatin a cloudinit configuration, and a proxy connection for VM communication over the endpoint internal network.
- inputs.yaml Contains hardware passthrough inputs for usb, serial, video, gpu, and generic pcie devices and other inputs. To leverage these inputs in a deployment change the "hidden:" value to "false". When set to false, these inputs will be visible during blueprint deploymet.

### 'mqtt_nodered' directory

- definitions.yaml contains logic for running ansible playbooks from the playbooks directory. Modify to add addtional node tasks based on the use case.
- The default playbooks install docker engine on the Virtual Machine then run docker compose for nginx, mqtt, and nodered.

### 'nginx_app' directory

- definitions.yaml contains logic for running commands using the Fabric plugin. Modify to add addtional commands or node tasks based on the use case.
- The commands clone a public git repository and run the script with the specified environment variables, which installs a basic NGINX web app for serving static files using ssl.

### 'container_based' directory

- definitions.yaml contains logic for running the NativeEdgeCompose node for deploying containers directly on the NativeEdge endpoint
- The inputs and compose/mfg-tools_compose.yaml may be modified to leverage different container deployments based on the usecase

### 'remotehost' directory

- definitions.yaml leverages the same Fabric plugin and commands as the nginx_app but instead disables the proxy connection allowing the blueprint to be run on any supported 3rd-party client.
- The inputs and definitions may be modified to provide different results

## Advanced Considerations

When using NAT Port Forward Rules, the following is required:

- NAT type Virtual Network Segment must be selected
- host_ip must equal the Host Network IP from the interface where the NAT is created
- host_port is the port to connect on from the host_ip
- protocol must equal TCP or UDP
- service_type must be HTTP, SSH, or CUSTOM
- vm_ip may be left blank if DHCP is used
- vm_port is the local port of the application to forward
