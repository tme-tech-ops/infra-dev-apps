import bcrypt
from dell import ctx
from dell.state import ctx_parameters as inputs

vm_passwd_input = inputs.get('vm_password')

def hash_vm_passwd(plain_password: str) -> str:
    """Hash a plain password using bcrypt.

    The DAP deployment agent runs Python 3.14, which removed the stdlib
    `crypt` module; bcrypt is used here to match the reference
    edge-cloudinit-linux blueprint. cloud-init accepts bcrypt ($2b$) hashes
    in the user `passwd` field.
    """
    return bcrypt.hashpw(
        plain_password.encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')

hashed_vm_password = hash_vm_passwd(vm_passwd_input)
ctx.instance.runtime_properties['hashed_vm_passwd'] = hashed_vm_password