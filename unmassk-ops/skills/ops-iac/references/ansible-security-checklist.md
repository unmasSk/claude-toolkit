# Ansible Security Checklist

## Secrets management

### Bad practices

```yaml
# Hardcoded passwords
- name: Create user
  ansible.builtin.user:
    name: admin
    password: "P@ssw0rd123"  # NEVER DO THIS

# Hardcoded API keys in vars
vars:
  api_key: "sk-1234567890abcdef"  # NEVER DO THIS
  db_password: "secret123"         # NEVER DO THIS
```

### Good practices

```yaml
# Use Ansible Vault for sensitive data
- name: Create user
  ansible.builtin.user:
    name: admin
    password: "{{ admin_password | password_hash('sha512') }}"
  no_log: true

# Load vaulted variables
- name: Include vaulted vars
  ansible.builtin.include_vars:
    file: secrets.yml  # Encrypted with ansible-vault

# Use external secret management
- name: Fetch secret from HashiCorp Vault
  ansible.builtin.set_fact:
    db_password: "{{ lookup('community.hashi_vault.hashi_vault', 'secret/data/db:password') }}"
  no_log: true
```

Vault operations:

```bash
ansible-vault create secrets.yml
ansible-vault encrypt existing_file.yml
ansible-vault decrypt secrets.yml
ansible-vault edit secrets.yml
```

Rules:
- Always use Ansible Vault for sensitive data
- Never commit unencrypted secrets to version control
- Use `no_log: true` for all tasks that handle secrets
- Use different vault passwords per environment
- Rotate secrets regularly

---

## Privilege escalation

### Bad practices

```yaml
# Unnecessary play-wide become
- hosts: all
  become: true
  tasks:
    - name: Check application status
      ansible.builtin.command: systemctl status myapp

    - name: Read configuration
      ansible.builtin.slurp:
        src: /etc/myapp/config.yml
```

### Good practices

```yaml
- hosts: all
  tasks:
    - name: Check application status
      ansible.builtin.command: systemctl status myapp
      # No become needed for read-only systemctl

    - name: Install package
      ansible.builtin.apt:
        name: nginx
        state: present
      become: true  # Only escalate where needed

    - name: Configure application
      ansible.builtin.template:
        src: config.j2
        dest: /etc/myapp/config.yml
        owner: myapp
        group: myapp
        mode: '0640'
      become: true
```

Rules:
- Principle of least privilege — only escalate where necessary
- Use specific `become_user` instead of always root
- Restrict sudo access in sudoers to specific commands
- Audit all `become: true` usage

---

## File permissions

### Permission reference table

| File type | Mode | Owner | Group |
|-----------|------|-------|-------|
| Private keys | 0600 | user | user |
| Public keys | 0644 | user | user |
| Config files (sensitive) | 0640 | app | app |
| Config files (public) | 0644 | app | app |
| Executables | 0755 | root | root |
| Directories (sensitive) | 0750 | app | app |
| Directories (public) | 0755 | app | app |
| Log files | 0640 | app | app |

### Bad practices

```yaml
# World-readable private key
- ansible.builtin.copy:
    src: id_rsa
    dest: /home/user/.ssh/id_rsa
    mode: '0644'  # Wrong

# No mode specified — depends on umask
- ansible.builtin.template:
    src: database.conf.j2
    dest: /etc/app/database.conf

# World-writable
- ansible.builtin.copy:
    src: deploy.sh
    dest: /usr/local/bin/deploy.sh
    mode: '0777'  # Wrong
```

### Good practices

```yaml
- ansible.builtin.copy:
    src: id_rsa
    dest: /home/user/.ssh/id_rsa
    owner: user
    group: user
    mode: '0600'

- ansible.builtin.template:
    src: database.conf.j2
    dest: /etc/app/database.conf
    owner: appuser
    group: appgroup
    mode: '0640'

- ansible.builtin.file:
    path: /etc/app/secrets
    state: directory
    owner: appuser
    group: appgroup
    mode: '0750'
```

---

## Command injection prevention

### Bad practices

```yaml
# Unvalidated user input
- ansible.builtin.shell: "cat {{ user_provided_filename }}"
  # Vulnerable: user could inject "; rm -rf /"

# Using shell when a module exists
- ansible.builtin.shell: "mkdir -p {{ directory_name }}"
```

### Good practices

```yaml
# Use the file module instead of shell mkdir
- ansible.builtin.file:
    path: "{{ directory_name }}"
    state: directory
    mode: '0755'

# When shell is unavoidable, use quote filter and validate input
- ansible.builtin.shell: "cat {{ user_provided_filename | quote }}"
  when: user_provided_filename is match('^[a-zA-Z0-9._-]+$')

# Validate search terms before use
- ansible.builtin.command: "grep {{ search_term }} /var/log/app.log"
  when:
    - search_term is defined
    - search_term | length > 0
    - search_term is match('^[a-zA-Z0-9 ]+$')
```

Rules:
- Prefer modules over `command`/`shell`
- Always use `| quote` filter for variables in shell commands
- Validate input with allowlist regex patterns
- Never trust user-provided input without validation

---

## Network security

### Bad practices

```yaml
# HTTP instead of HTTPS
- ansible.builtin.get_url:
    url: http://example.com/file.tar.gz

# SSL verification disabled
- ansible.builtin.uri:
    url: https://api.example.com/data
    validate_certs: false

# Binding to all interfaces
vars:
  bind_address: "0.0.0.0"
```

### Good practices

```yaml
- ansible.builtin.get_url:
    url: https://example.com/file.tar.gz
    checksum: sha256:abc123...

- ansible.builtin.uri:
    url: https://api.example.com/data
    validate_certs: true

vars:
  bind_address: "127.0.0.1"

- name: Allow port only from internal network
  community.general.ufw:
    rule: allow
    port: '443'
    proto: tcp
    src: '10.0.0.0/8'
```

---

## SELinux and AppArmor

```yaml
- name: Configure SELinux enforcing
  ansible.builtin.command: setenforce 1
  changed_when: false

- name: Set SELinux context for web content
  ansible.builtin.command: chcon -Rv -t httpd_sys_content_t /web/content
  changed_when: false

- name: Load AppArmor profile
  ansible.builtin.command: apparmor_parser -r /etc/apparmor.d/usr.bin.myapp
  changed_when: false
```

Do not disable SELinux or AppArmor in production playbooks.

---

## Audit and logging

```yaml
- name: Create admin user
  ansible.builtin.user:
    name: admin
    groups: sudo
    state: present
  register: admin_user_result

- name: Log user creation
  ansible.builtin.lineinfile:
    path: /var/log/ansible-changes.log
    line: "{{ ansible_date_time.iso8601 }} - Admin user created by {{ ansible_user_id }}"
    create: true
  when: admin_user_result.changed
```

---

## Security validation checklist

Before running playbooks in production:

- [ ] No hardcoded secrets (passwords, API keys, tokens)
- [ ] All sensitive data encrypted with Ansible Vault
- [ ] `no_log: true` used for tasks handling secrets
- [ ] `become: true` used only where necessary
- [ ] File permissions explicitly set on all created/copied files
- [ ] Private keys have mode 0600
- [ ] No world-writable files or directories
- [ ] Input validated for user-provided variables
- [ ] Specific modules used instead of `command`/`shell` where possible
- [ ] `| quote` used for variables in shell commands
- [ ] HTTPS used instead of HTTP
- [ ] `validate_certs: true` (default) not overridden
- [ ] Services bound to specific interfaces, not `0.0.0.0`
- [ ] Firewall rules configured appropriately
- [ ] SELinux/AppArmor not disabled
- [ ] Security-relevant actions logged
- [ ] `ansible-lint --profile security` passes

---

## Security scanning tools

```bash
# ansible-lint with security profile
ansible-lint --profile security playbook.yml

# Scan for secrets in files
git secrets --scan

# Trivy config scan
trivy config .
```
