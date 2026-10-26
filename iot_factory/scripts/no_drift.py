"""check_drift for the Ansible nodes that have nothing to update.

preflight, install_docker, verify_demo, accept_joins and join_hub read inputs
that a deployment update can change (for example the ports). Without this, the
ansible-plugin's own check_drift runs (and fails: store_facts is off), and a
changed property would make DAP reinstall the node. Reporting no drift leaves
them alone; deploy_stack's check_drift, preupdate (preflight) and postupdate
(verify_demo) cover the stack. Accept/join on-off is handled by instance
scaling, not by drift.
"""
from dell import ctx

ctx.logger.info(f"{ctx.node.id}: nothing to update")
ctx.returns(None)
