# Ansible Best Practices

## Directory structure

### Standard playbook layout

```
playbook.yml
roles/
  common/
    tasks/
      main.yml
    handlers/
      main.yml
    templates/
    files/
    vars/
      main.yml
    defaults/
      main.yml
    meta/
      main.yml
inventory/
  production/
    hosts
    group_vars/
    host_vars/
  staging/
    hosts
    group_vars/
    host_vars/
```

### Role subdirectories

| Directory | Purpose |
|-----------|---------|
| `tasks/main.yml` | Main task list |
| `handlers/main.yml` | Handlers triggered by tasks |
| `templates/` | Jinja2 templates |
| `files/` | Static files to copy |
| `vars/main.yml` | Role-specific variables (high priority, not overridable) |
| `defaults/main.yml` | Default variables (low priority, overridable by inventory/play) |
| `meta/main.yml` | Role dependencies and Galaxy metadata |

---

## Naming conventions

### Files and directories

- Lowercase with underscores: `install_nginx.yml`, `backup_database.yml`
- Playbook files end in `.yml`
- Role names: short, lowercase, underscores

### Variables

- `snake_case` only — no camelCase or kebab-case
- Descriptive: `nginx_port`, `db_backup_dir`, `app_version`
- Prefix role-specific vars with role name: `nginx_worker_processes`

### Tasks

- Start with a verb: "Install nginx", "Copy configuration file", "Start service"

---

## Task best practices

### Always declare state

```yaml
# Good
- name: Ensure nginx is installed
  ansible.builtin.package:
    name: nginx
    state: present

# Bad — missing state
- name: Install nginx
  ansible.builtin.package:
    name: nginx
```

### Use Fully Qualified Collection Names (FQCN)

Required for Ansible 2.10+. Short names are deprecated.

```yaml
# Good
- name: Copy configuration file
  ansible.builtin.copy:
    src: nginx.conf
    dest: /etc/nginx/nginx.conf

# Bad
- name: Copy configuration file
  copy:
    src: nginx.conf
    dest: /etc/nginx/nginx.conf
```

### Idempotency

All tasks must be safe to run multiple times.

```yaml
# Good — idempotent
- name: Create directory
  ansible.builtin.file:
    path: /opt/app
    state: directory
    mode: '0755'

# Bad — not idempotent
- name: Create directory
  ansible.builtin.command: mkdir -p /opt/app
```

When using `command` or `shell`, always use `creates`, `removes`, or `changed_when`:

```yaml
- name: Run install script
  ansible.builtin.command: /opt/install.sh
  args:
    creates: /opt/app/installed.flag
```

### Error handling

```yaml
- name: Attempt to start service
  ansible.builtin.service:
    name: myapp
    state: started
  register: service_result
  failed_when: false

- name: Handle service failure
  ansible.builtin.debug:
    msg: "Service failed to start: {{ service_result.msg }}"
  when: service_result.failed
```

---

## Variable precedence (high to low)

1. Extra vars (`-e` in CLI)
2. Task vars
3. Block vars
4. Role and include vars
5. Set_facts / registered vars
6. Play vars
7. Play vars_files
8. Role defaults
9. Inventory vars (host_vars, group_vars)

### Using variables

```yaml
- name: Set port with default
  ansible.builtin.set_fact:
    app_port: "{{ custom_port | default(8080) }}"

- name: Create full path
  ansible.builtin.set_fact:
    config_path: "{{ base_dir }}/{{ app_name }}/config.yml"
```

---

## Conditionals and loops

```yaml
- name: Install on Debian-based systems
  ansible.builtin.apt:
    name: nginx
    state: present
  when: ansible_os_family == "Debian"

- name: Install packages
  ansible.builtin.package:
    name: "{{ item }}"
    state: present
  loop:
    - nginx
    - postgresql
    - redis

- name: Create users
  ansible.builtin.user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
    state: present
  loop:
    - { name: 'alice', groups: 'admin,developers' }
    - { name: 'bob', groups: 'developers' }
```

---

## Handlers

Handlers run once at the end of a play, after all tasks complete. Use `meta: flush_handlers` to run them immediately.

```yaml
# tasks/main.yml
- name: Copy nginx configuration
  ansible.builtin.copy:
    src: nginx.conf
    dest: /etc/nginx/nginx.conf
  notify: Restart nginx

# handlers/main.yml
- name: Restart nginx
  ansible.builtin.service:
    name: nginx
    state: restarted
```

---

## Templates (Jinja2)

```yaml
- name: Deploy configuration from template
  ansible.builtin.template:
    src: app_config.j2
    dest: /etc/app/config.yml
    mode: '0644'
    backup: true
```

```jinja2
{# templates/app_config.j2 #}
server:
  port: {{ app_port }}
  host: {{ ansible_default_ipv4.address }}

database:
  host: {{ db_host }}
  port: {{ db_port | default(5432) }}
  name: {{ db_name }}

{% if enable_ssl %}
ssl:
  enabled: true
  cert: {{ ssl_cert_path }}
  key: {{ ssl_key_path }}
{% endif %}
```

### Common Jinja2 filters

```yaml
# String manipulation
- ansible.builtin.set_fact:
    upper: "{{ text | upper }}"
    trimmed: "{{ '  text  ' | trim }}"
    replaced: "{{ text | replace('old', 'new') }}"

# List and dict operations
- ansible.builtin.set_fact:
    unique_items: "{{ my_list | unique }}"
    combined: "{{ dict1 | combine(dict2) }}"
    names: "{{ users | map(attribute='name') | list }}"

# Default and mandatory
- ansible.builtin.set_fact:
    port: "{{ custom_port | default(8080) }}"
    required_value: "{{ must_be_defined | mandatory }}"

# Encoding
- ansible.builtin.set_fact:
    b64: "{{ 'text' | b64encode }}"
    decoded: "{{ encoded_value | b64decode }}"

# Password hashing
- ansible.builtin.user:
    name: myuser
    password: "{{ user_password | password_hash('sha512', 'mysecretsalt') }}"
```

### Lookup plugins

```yaml
# Read file content
- ansible.builtin.authorized_key:
    user: deploy
    key: "{{ lookup('file', '/home/user/.ssh/id_rsa.pub') }}"

# Environment variable
- ansible.builtin.set_fact:
    home_dir: "{{ lookup('env', 'HOME') }}"

# query() always returns a list — prefer over lookup() in loops
- ansible.builtin.debug:
    msg: "{{ item }}"
  loop: "{{ query('inventory_hostnames', 'all') }}"
```

---

## Security

```yaml
# Use no_log for sensitive tasks
- name: Set database password
  ansible.builtin.user:
    name: dbadmin
    password: "{{ db_password | password_hash('sha512') }}"
  no_log: true

# Sensitive file permissions
- name: Copy private key
  ansible.builtin.copy:
    src: id_rsa
    dest: /etc/ssl/private/app.key
    mode: '0600'
    owner: root
    group: root
```

Encrypt secrets with ansible-vault:

```bash
ansible-vault create secrets.yml
ansible-vault encrypt existing_file.yml
```

---

## Tags

```yaml
- name: Install packages
  ansible.builtin.package:
    name: nginx
    state: present
  tags:
    - packages
    - install

# ansible-playbook playbook.yml --tags "install"
# ansible-playbook playbook.yml --skip-tags "install"
```

Reserved tags: `always` (always runs), `never` (only runs when explicitly called).

---

## Testing and validation

```bash
# Syntax check
ansible-playbook playbook.yml --syntax-check

# Dry run
ansible-playbook playbook.yml --check --diff

# List tasks
ansible-playbook playbook.yml --list-tasks

# Run with tags
ansible-playbook playbook.yml --tags webserver

# Verbose output
ansible-playbook playbook.yml -vvv
```

```yaml
# In-playbook validation
- name: Verify configuration
  ansible.builtin.assert:
    that:
      - ansible_distribution in ['Ubuntu', 'Debian', 'CentOS', 'RedHat']
      - app_port | int > 0
      - app_port | int < 65536
    fail_msg: "Invalid configuration"
```

---

## Performance

```yaml
# Disable fact gathering when not needed
- hosts: all
  gather_facts: false
  tasks:
    - name: Ping
      ansible.builtin.ping:

# Rolling updates
- hosts: webservers
  serial: 2

# Async tasks
- name: Long running task
  ansible.builtin.command: /opt/long_running_script.sh
  async: 3600
  poll: 0
  register: long_task

- name: Check on long task
  ansible.builtin.async_status:
    jid: "{{ long_task.ansible_job_id }}"
  register: job_result
  until: job_result.finished
  retries: 30
  delay: 10
```

SSH pipelining (ansible.cfg):

```ini
[ssh_connection]
pipelining = True
```

Fact caching (ansible.cfg):

```ini
[defaults]
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 86400
```

---

## Module selection priority

1. `ansible.builtin.*` — always first choice
2. Official collection modules (`community.general.*`, `ansible.posix.*`)
3. Custom modules — only when no suitable module exists
4. `command` / `shell` — last resort; use `creates`/`removes`/`changed_when`

---

## Complete playbook example

```yaml
---
- name: Deploy web application
  hosts: webservers
  become: true
  vars:
    app_version: "1.2.3"
    app_port: 8080

  pre_tasks:
    - name: Update package cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"

  roles:
    - common
    - nginx
    - application

  post_tasks:
    - name: Verify application is running
      ansible.builtin.uri:
        url: "http://localhost:{{ app_port }}/health"
        status_code: 200
      register: health_check
      until: health_check.status == 200
      retries: 5
      delay: 10

  handlers:
    - name: Restart application
      ansible.builtin.service:
        name: myapp
        state: restarted
```

---

## Common pitfalls

1. Not using FQCN — always use fully qualified collection names
2. Hardcoded values — use variables
3. Not handling different OS families — check `ansible_os_family`
4. Non-idempotent tasks — safe to run multiple times
5. Restarting services in tasks instead of handlers
6. Secrets in plain text — use ansible-vault
7. Missing `--check` before production runs
8. Complex logic in playbooks — move to roles or modules
