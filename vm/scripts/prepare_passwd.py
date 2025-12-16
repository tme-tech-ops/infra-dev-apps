import crypt
from dell import ctx
from dell.state import ctx_parameters as inputs

vm_passwd_input = inputs.get('vm_password')

def hash_vm_passwd(plain_password: str) -> str:
    return crypt.crypt(plain_password, crypt.mksalt(crypt.METHOD_SHA512))

hashed_vm_password = hash_vm_passwd(vm_passwd_input)
ctx.instance.runtime_properties['hashed_vm_passwd'] = hashed_vm_password