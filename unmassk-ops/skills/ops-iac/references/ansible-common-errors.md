# Common Ansible Errors and Solutions

## Syntax errors

### mapping values are not allowed here

```
ERROR! Syntax Error while loading YAML.
  mapping values are not allowed here
```

Cause: unquoted colon in a value, or indentation error.

```yaml
# Bad
vars:
  db_host: localhost:5432

# Good
vars:
  db_host: "localhost:5432"
```

### found undefined alias

```
ERROR! Syntax Error while loading YAML.
  found undefined alias 'anchor'
```

Cause: YAML anchor used before it is defined. Define anchors before referencing them.

```yaml
common_packages: &common_packages
  - git
  - curl

- name: Install common packages
  ansible.builtin.apt:
    name: *common_packages
```

### could not find expected ':'

```
ERROR! could not find expected ':'
```

Cause: missing colon after a key.

```yaml
# Bad
- name Install package
  ansible.builtin.apt:
    name nginx

# Good
- name: Install package
  ansible.builtin.apt:
    name: nginx
```

---

## Module errors

### Unsupported parameters for module

```
ERROR! Unsupported parameters for (module) module: parameter_name
```

Cause: typo in parameter name or wrong parameter for this module.

```yaml
# Bad
- ansible.builtin.file:
    path: /tmp/test
    state: present
    mod: '0644'

# Good
- ansible.builtin.file:
    path: /tmp/test
    state: present
    mode: '0644'
```

Check correct parameters with `ansible-doc <module_name>`.

### MODULE FAILURE

```
fatal: [host]: FAILED! => {"changed": false, "module_stderr": "..."}
```

Common causes: Python not installed on target, wrong Python interpreter, SELinux blocking.

```yaml
# Specify Python interpreter in inventory
[webservers]
server1 ansible_python_interpreter=/usr/bin/python3

# Or in playbook vars
- hosts: all
  vars:
    ansible_python_interpreter: /usr/bin/python3
```

### Missing required arguments

```
fatal: [host]: FAILED! => {"msg": "missing required arguments: name"}
```

Add the missing parameter:

```yaml
# Bad
- ansible.builtin.apt:
    state: present

# Good
- ansible.builtin.apt:
    name: nginx
    state: present
```

---

## Template errors

### template error while templating string

```
fatal: [host]: FAILED! => {"msg": "An unhandled exception occurred while templating..."}
```

Cause: undefined variable, wrong filter syntax, or Jinja2 syntax error.

```yaml
# Provide a default
vars:
  port: "{{ app_port | default(8080) }}"

# Or require it explicitly
vars:
  port: "{{ app_port | mandatory('app_port must be defined') }}"

# Or guard with when
- name: Configure app
  ansible.builtin.template:
    src: config.j2
    dest: /etc/app/config.yml
  when: app_port is defined
```

### Unexpected templating type error

```
fatal: [host]: FAILED! => {"msg": "Unexpected templating type error occurred on (...)"}
```

Cause: wrong type — e.g., treating an integer as a string.

```yaml
port: "{{ app_port | string }}"
replicas: "{{ replica_count | int }}"
enabled: "{{ feature_enabled | bool }}"
```

---

## Connection errors

### Failed to connect to the host via ssh

```
fatal: [host]: UNREACHABLE! => {"msg": "Failed to connect to the host via ssh"}
```

```bash
# Test SSH manually
ssh user@host

# Ping via Ansible
ansible host -m ping

# Specify key
ansible-playbook -i inventory playbook.yml --private-key=~/.ssh/id_rsa

# Inventory options
[webservers]
server1 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa
```

### Permission denied (publickey)

```bash
# Copy key to target
ssh-copy-id user@host

# Check agent
ssh-add -l
ssh-add ~/.ssh/id_rsa

# Inventory option
server1 ansible_ssh_private_key_file=~/.ssh/custom_key
```

### Authentication or permission failure

```yaml
# Password auth (use vault for the password itself)
- hosts: all
  vars:
    ansible_ssh_pass: "{{ vault_ssh_pass }}"
    ansible_become_pass: "{{ vault_become_pass }}"
```

Or use `--ask-pass --ask-become-pass` at runtime.

---

## Privilege escalation errors

### Missing sudo password

```bash
# Provide at runtime
ansible-playbook -i inventory playbook.yml --ask-become-pass

# Or configure passwordless sudo on target
# /etc/sudoers.d/ansible
ansible_user ALL=(ALL) NOPASSWD: ALL
```

### Permission denied writing files

Add `become: true` at task or play level:

```yaml
- name: Install package
  ansible.builtin.apt:
    name: nginx
    state: present
  become: true
```

---

## Variable errors

### The task includes an option with an undefined variable

```
fatal: [host]: FAILED! => {"msg": "The task includes an option with an undefined variable..."}
```

```yaml
# Default value
- ansible.builtin.debug:
    msg: "{{ my_var | default('default_value') }}"

# Guard with when
- ansible.builtin.debug:
    msg: "{{ my_var }}"
  when: my_var is defined
```

### Invalid characters in group names

```
[WARNING]: Invalid characters were found in group names
```

Cause: hyphens or spaces in group names. Use underscores.

```ini
# Bad
[web-servers]

# Good
[web_servers]
```

---

## Inventory errors

### Could not match supplied host pattern

```
[WARNING]: Could not match supplied host pattern, ignoring: webservers
```

Cause: group not defined in inventory. Check inventory file.

```ini
[webservers]
web1.example.com
web2.example.com
```

### Unable to parse inventory

Cause: mixing INI and YAML syntax in same file.

```ini
# Correct INI format
[webservers]
web1 ansible_host=192.168.1.10
web2 ansible_host=192.168.1.11
```

---

## Loop errors

### Invalid data passed to 'loop'

```
fatal: [host]: FAILED! => {"msg": "Invalid data passed to 'loop', it requires a list"}
```

`loop` requires a list, not a scalar:

```yaml
# Bad
loop: nginx

# Good
loop:
  - nginx
  - python3
```

### with_items deprecation warning

Replace `with_items` with `loop`:

```yaml
# Deprecated
- ansible.builtin.apt:
    name: "{{ item }}"
  with_items:
    - nginx

# Current
- ansible.builtin.apt:
    name: "{{ item }}"
  loop:
    - nginx
```

---

## Handler errors

### Handler not found

```
ERROR! The requested handler 'restart nginx' was not found
```

Handler name must match the `notify` string exactly (case-sensitive).

```yaml
# tasks/main.yml
- name: Configure nginx
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  notify: restart nginx

# handlers/main.yml
- name: restart nginx
  ansible.builtin.systemd:
    name: nginx
    state: restarted
```

---

## Include/import errors

### Unable to retrieve file contents

```
fatal: [host]: FAILED! => {"msg": "Unable to retrieve file contents. Could not find or access 'file.yml'"}
```

Paths are relative to the playbook location:

```yaml
# Include from same directory
- ansible.builtin.include_tasks: install.yml

# Or use full path from role
- ansible.builtin.include_tasks: roles/common/tasks/install.yml
```

---

## Collection errors

### couldn't resolve module/action

```
ERROR! couldn't resolve module/action 'community.general.docker_container'
```

Install the missing collection:

```bash
ansible-galaxy collection install community.general

# From requirements.yml
ansible-galaxy collection install -r requirements.yml
```

### Collection version conflict

```bash
# Force reinstall
ansible-galaxy collection install community.general --force

# Install specific version
ansible-galaxy collection install community.general:5.0.0
```

---

## Check mode errors

### This module does not support check mode

```yaml
- name: Command that doesn't support check mode
  ansible.builtin.command: /usr/local/bin/custom-script.sh
  check_mode: false  # Always run, even in --check mode
```

---

## Performance issues

Slow execution:

1. Enable SSH pipelining in `ansible.cfg`:
   ```ini
   [ssh_connection]
   pipelining = True
   ```

2. Enable fact caching:
   ```ini
   [defaults]
   gathering = smart
   fact_caching = jsonfile
   fact_caching_connection = /tmp/ansible_facts
   fact_caching_timeout = 86400
   ```

3. Disable fact gathering when not needed:
   ```yaml
   - hosts: all
     gather_facts: false
   ```

4. Process hosts in batches:
   ```yaml
   - hosts: all
     serial: 10
   ```

---

## Pre-run checklist

```bash
# Format check
yamllint playbook.yml

# Lint
ansible-lint playbook.yml

# Syntax check
ansible-playbook playbook.yml --syntax-check

# Dry run
ansible-playbook playbook.yml --check --diff

# Test on subset
ansible-playbook playbook.yml --limit webserver1

# Verbose output
ansible-playbook playbook.yml -vvv

# Step through tasks
ansible-playbook playbook.yml --step
```
