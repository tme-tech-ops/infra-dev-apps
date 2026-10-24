# Stdout callback for the IoT Smart Factory playbooks.
#
# The DAP ansible-plugin always runs ansible-playbook with at least -v, and at
# -v the default callback dumps every task result into the deployment log.
# This callback is the default callback with one verbosity level taken off, so
# debug_level 0/1 gives one line per task, and 2/3 still add detail.
from ansible.plugins.callback.default import CallbackModule as DefaultCallback
from ansible.utils.display import Display

DOCUMENTATION = '''
    name: iot_factory
    type: stdout
    short_description: default output without the forced -v result dumps
    description:
      - The default callback, rendered one verbosity level lower.
    extends_documentation_fragment:
      - default_callback
      - result_format_callback
'''


class CallbackModule(DefaultCallback):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'iot_factory'

    def __init__(self):
        super().__init__()
        display = Display()
        if display.verbosity > 0:
            display.verbosity -= 1
