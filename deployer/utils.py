import os
import json
import tempfile
import subprocess
from ruamel.yaml import YAML
from ruamel.yaml.scanner import ScannerError
from contextlib import contextmanager

yaml = YAML(typ='safe', pure=True)

@contextmanager
def decrypt_file(encrypted_path):
    """
    Provide secure temporary decrypted contents of a given file

    If file isn't a sops encrypted file, we assume no encryption is used
    and return the current path.
    """
    # We must first determine if the file is using sops
    # sops files are JSON/YAML with a `sops` key. So we first check
    # if the file is valid JSON/YAML, and then if it has a `sops` key
    with open(encrypted_path) as f:
        _, ext = os.path.splitext(encrypted_path)
        # Support the (clearly wrong) people who use .yml instead of .yaml
        if ext == '.yaml' or ext == '.yml':
            try:
                encrypted_data = yaml.load(f)
            except ScannerError:
                yield encrypted_path
                return
        elif ext == '.json':
            try:
                encrypted_data = json.load(f)
            except json.JSONDecodeError:
                yield encrypted_path
                return

    if 'sops' not in encrypted_data:
        yield encrypted_path
        return

    # If file has a `sops` key, we assume it's sops encrypted
    with tempfile.NamedTemporaryFile() as f:
        subprocess.check_call([
            'sops',
            '--output', f.name,
            '--decrypt', encrypted_path
        ])
        yield f.name

def replace_staff_placeholder(user_list, staff):
    """
    Replace the staff placeholder with the actual list
    of staff members in the user_list.
    """
    if isinstance(user_list, str):
        user_list = [user_list]

    custom_users = user_list[:]
    for staff_list_type, staff_ids in staff.items():
        staff_placeholder = "<staff_" + staff_list_type + ">"
        if staff_placeholder in user_list:
            custom_users.remove(staff_placeholder)

            return custom_users + staff_ids

def update_authenticator_config(config, template):
    """Prepare a hub's configuration file for deployment."""
    # Load the staff config file
    with open('config/hubs/staff.yaml') as f:
        staff = yaml.load(f)

    if "basehub" in template:
        authenticator = config.get("jupyterhub", {}).get("hub", {}).get("config", {}).get("Authenticator", {})
    else:
        # Right now all the other templates inherit from basehub, fix this if things change
        authenticator = config.get("basehub", {}).get("jupyterhub", {}).get("hub", {}).get("config", {}).get("Authenticator", {})

    # `Allowed_users` list doesn't exist for hubs where everyone is allowed to login
    if authenticator.get("allowed_users", None) is not None:
        authenticator["allowed_users"] = replace_staff_placeholder(authenticator["allowed_users"], staff["staff"])

    authenticator["admin_users"] = replace_staff_placeholder(authenticator["admin_users"], staff["staff"])
