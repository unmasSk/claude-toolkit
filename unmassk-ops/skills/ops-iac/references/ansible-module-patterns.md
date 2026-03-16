# Common Ansible Module Usage Patterns

## Package management

### ansible.builtin.package (OS-agnostic)

```yaml
- name: Install package
  ansible.builtin.package:
    name: nginx
    state: present
```

### ansible.builtin.apt (Debian/Ubuntu)

```yaml
- name: Install package
  ansible.builtin.apt:
    name: nginx
    state: present
    update_cache: true
    cache_valid_time: 3600

- name: Install specific version
  ansible.builtin.apt:
    name: nginx=1.18.0-0ubuntu1
    state: present

- name: Install multiple packages
  ansible.builtin.apt:
    name:
      - nginx
      - postgresql
      - redis-server
    state: present
```

### ansible.builtin.dnf (RHEL 8+/CentOS 8+)

```yaml
- name: Install package
  ansible.builtin.dnf:
    name: nginx
    state: present
    update_cache: true
    enablerepo: epel  # Optional
```

### ansible.builtin.yum (RHEL 7/CentOS 7 only)

Use `ansible.builtin.dnf` for RHEL 8+. Use `yum` only for RHEL 7 targets.

---

## File operations

### ansible.builtin.file

```yaml
- name: Create directory
  ansible.builtin.file:
    path: /opt/app/config
    state: directory
    mode: '0755'
    owner: appuser
    group: appgroup

- name: Create symlink
  ansible.builtin.file:
    src: /opt/app/current
    dest: /opt/app/releases/v1.2.3
    state: link

- name: Remove file
  ansible.builtin.file:
    path: /tmp/tempfile
    state: absent
```

### ansible.builtin.copy

```yaml
- name: Copy file from control node
  ansible.builtin.copy:
    src: files/nginx.conf
    dest: /etc/nginx/nginx.conf
    mode: '0644'
    owner: root
    group: root
    backup: true
    validate: 'nginx -t -c %s'

- name: Create file with inline content
  ansible.builtin.copy:
    content: |
      server {
        listen 80;
        server_name example.com;
      }
    dest: /etc/nginx/sites-available/example
    mode: '0644'

- name: Copy file on remote host
  ansible.builtin.copy:
    src: /tmp/source.txt
    dest: /opt/destination.txt
    remote_src: true
```

### ansible.builtin.template

```yaml
- name: Deploy configuration from template
  ansible.builtin.template:
    src: templates/app_config.j2
    dest: /etc/app/config.yml
    mode: '0644'
    owner: appuser
    group: appgroup
    backup: true
    validate: '/usr/bin/app validate %s'
```

### ansible.builtin.fetch

```yaml
- name: Fetch file from remote
  ansible.builtin.fetch:
    src: /var/log/app/error.log
    dest: /tmp/logs/{{ inventory_hostname }}/
    flat: true
```

### ansible.builtin.lineinfile

```yaml
- name: Ensure line is present
  ansible.builtin.lineinfile:
    path: /etc/hosts
    line: '192.168.1.100 app.local'
    state: present

- name: Replace line matching regexp
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PermitRootLogin'
    line: 'PermitRootLogin no'
    backup: true
  notify: Restart sshd

- name: Remove matching line
  ansible.builtin.lineinfile:
    path: /etc/hosts
    regexp: '.*old-server.*'
    state: absent
```

### ansible.builtin.blockinfile

```yaml
- name: Add block of text
  ansible.builtin.blockinfile:
    path: /etc/hosts
    block: |
      192.168.1.10 web1.local
      192.168.1.11 web2.local
    marker: "# {mark} ANSIBLE MANAGED BLOCK"
    backup: true
```

---

## Service management

### ansible.builtin.service

```yaml
- name: Ensure service is running
  ansible.builtin.service:
    name: nginx
    state: started
    enabled: true

- name: Restart service
  ansible.builtin.service:
    name: nginx
    state: restarted
```

### ansible.builtin.systemd

```yaml
- name: Reload systemd and start service
  ansible.builtin.systemd:
    name: myapp
    state: started
    enabled: true
    daemon_reload: true

- name: Mask service
  ansible.builtin.systemd:
    name: apache2
    masked: true
```

---

## User and group management

### ansible.builtin.user

```yaml
- name: Create user
  ansible.builtin.user:
    name: appuser
    uid: 1500
    group: appgroup
    groups: docker,sudo
    shell: /bin/bash
    home: /home/appuser
    createhome: true
    state: present

- name: Set user password
  ansible.builtin.user:
    name: appuser
    password: "{{ user_password | password_hash('sha512') }}"
    update_password: always
```

### ansible.builtin.group

```yaml
- name: Create group
  ansible.builtin.group:
    name: appgroup
    gid: 1500
    state: present
```

### ansible.posix.authorized_key

```yaml
- name: Add SSH authorized key
  ansible.posix.authorized_key:
    user: appuser
    state: present
    key: "{{ lookup('file', '/home/user/.ssh/id_rsa.pub') }}"
```

---

## Command execution

Use specific modules instead of `command`/`shell` whenever possible.

### ansible.builtin.command

```yaml
- name: Run command without shell processing
  ansible.builtin.command: /usr/bin/make install
  args:
    chdir: /opt/app
    creates: /opt/app/bin/app
  register: make_result
  changed_when: make_result.rc == 0
```

### ansible.builtin.shell

```yaml
- name: Run shell command (needs pipes/redirects)
  ansible.builtin.shell: cat /var/log/app.log | grep ERROR > /tmp/errors.txt
  args:
    executable: /bin/bash
  changed_when: false
```

### ansible.builtin.script

```yaml
- name: Run script from control node
  ansible.builtin.script: scripts/setup.sh
  args:
    creates: /etc/app/setup.done
```

---

## Network and HTTP

### ansible.builtin.get_url

```yaml
- name: Download file
  ansible.builtin.get_url:
    url: https://example.com/file.tar.gz
    dest: /tmp/file.tar.gz
    mode: '0644'
    checksum: sha256:abc123...
```

### ansible.builtin.uri

```yaml
- name: Check API endpoint
  ansible.builtin.uri:
    url: http://localhost:8080/health
    method: GET
    status_code: 200
  register: health_check
  until: health_check.status == 200
  retries: 5
  delay: 10

- name: POST to API
  ansible.builtin.uri:
    url: https://api.example.com/deploy
    method: POST
    body_format: json
    body:
      version: "1.2.3"
    headers:
      Authorization: "Bearer {{ api_token }}"
    status_code: [200, 201]
```

---

## Git

### ansible.builtin.git

```yaml
- name: Clone repository
  ansible.builtin.git:
    repo: https://github.com/user/repo.git
    dest: /opt/app
    version: main
    force: true

- name: Clone with SSH key
  ansible.builtin.git:
    repo: git@github.com:user/repo.git
    dest: /opt/app
    key_file: /home/deploy/.ssh/id_rsa
    accept_hostkey: true
```

---

## Archives

### ansible.builtin.unarchive

```yaml
- name: Extract archive from control node
  ansible.builtin.unarchive:
    src: files/app.tar.gz
    dest: /opt/
    owner: appuser
    group: appgroup

- name: Download and extract
  ansible.builtin.unarchive:
    src: https://example.com/app.tar.gz
    dest: /opt/
    remote_src: true
```

### ansible.builtin.archive

```yaml
- name: Create archive
  ansible.builtin.archive:
    path:
      - /opt/app/config
      - /opt/app/data
    dest: /tmp/backup.tar.gz
    format: gz
```

---

## Cron

### ansible.builtin.cron

```yaml
- name: Add cron job
  ansible.builtin.cron:
    name: "Daily backup"
    minute: "0"
    hour: "2"
    job: "/opt/backup.sh"
    user: root
    state: present

- name: Remove cron job
  ansible.builtin.cron:
    name: "Daily backup"
    state: absent
```

---

## Debug and assert

### ansible.builtin.debug

```yaml
- name: Print variable
  ansible.builtin.debug:
    var: ansible_distribution

- name: Print message
  ansible.builtin.debug:
    msg: "Server IP: {{ ansible_default_ipv4.address }}"
```

### ansible.builtin.assert

```yaml
- name: Validate configuration
  ansible.builtin.assert:
    that:
      - ansible_distribution in ['Ubuntu', 'Debian']
      - app_port | int > 0
      - app_port | int < 65536
      - db_password is defined
    fail_msg: "Configuration validation failed"
```

---

## File search and status

### ansible.builtin.find

```yaml
- name: Find log files older than 7 days
  ansible.builtin.find:
    paths: /var/log
    patterns: "*.log"
    age: "7d"
    age_stamp: mtime
  register: old_logs

- name: Delete old log files
  ansible.builtin.file:
    path: "{{ item.path }}"
    state: absent
  loop: "{{ old_logs.files }}"
```

### ansible.builtin.stat

```yaml
- name: Check if config file exists
  ansible.builtin.stat:
    path: /etc/app/config.yml
  register: config_file

- name: Create config if missing
  ansible.builtin.copy:
    content: "default: config"
    dest: /etc/app/config.yml
  when: not config_file.stat.exists

- name: Fail if secret key not owned by root
  ansible.builtin.fail:
    msg: "Secret file must be owned by root"
  when:
    - config_file.stat.exists
    - config_file.stat.pw_name != 'root'
```

---

## Wait operations

### ansible.builtin.wait_for

```yaml
- name: Wait for port to be available
  ansible.builtin.wait_for:
    port: 8080
    delay: 5
    timeout: 300
    state: started

- name: Wait for file to exist
  ansible.builtin.wait_for:
    path: /opt/app/ready
    state: present
    timeout: 300
```

---

## Error handling with block/rescue/always

```yaml
- name: Deploy with rollback
  block:
    - name: Stop application
      ansible.builtin.service:
        name: myapp
        state: stopped

    - name: Deploy new version
      ansible.builtin.copy:
        src: app-v2.jar
        dest: /opt/app/app.jar
        backup: true
      register: deploy_result

    - name: Start application
      ansible.builtin.service:
        name: myapp
        state: started
  rescue:
    - name: Rollback on failure
      ansible.builtin.copy:
        remote_src: true
        src: "{{ deploy_result.backup_file }}"
        dest: /opt/app/app.jar
      when: deploy_result.backup_file is defined

    - name: Start application with old version
      ansible.builtin.service:
        name: myapp
        state: started
  always:
    - name: Verify application is running
      ansible.builtin.wait_for:
        port: 8080
        timeout: 60
```

In `rescue`, use `ansible_failed_task.name` and `ansible_failed_result.msg` to access error context.

---

## Advanced control flow

### delegate_to

```yaml
- name: Add server to load balancer
  ansible.builtin.uri:
    url: "http://lb.example.com/api/add"
    method: POST
    body_format: json
    body:
      server: "{{ inventory_hostname }}"
  delegate_to: localhost

- name: Run database migration (once on first db host)
  ansible.builtin.command: /opt/migrate.sh
  delegate_to: "{{ groups['database'] | first }}"
```

### run_once

```yaml
- name: Register all hosts in monitoring
  ansible.builtin.uri:
    url: https://monitoring.example.com/api/register
    method: POST
    body_format: json
    body:
      hostname: "{{ item }}"
  loop: "{{ ansible_play_hosts }}"
  run_once: true
  delegate_to: localhost
```

---

## Community collection modules (selected)

### community.general.ufw

```yaml
- name: Allow SSH
  community.general.ufw:
    rule: allow
    port: '22'
    proto: tcp

- name: Enable firewall
  community.general.ufw:
    state: enabled
```

### community.general.timezone

```yaml
- name: Set timezone
  community.general.timezone:
    name: America/New_York
```

### community.docker.docker_container

```yaml
- name: Run Docker container
  community.docker.docker_container:
    name: myapp
    image: nginx:latest
    state: started
    restart_policy: always
    ports:
      - "80:80"
    volumes:
      - /opt/data:/data
    env:
      APP_ENV: production
```

### ansible.posix.mount

```yaml
- name: Mount filesystem
  ansible.posix.mount:
    path: /data
    src: /dev/sdb1
    fstype: ext4
    state: mounted
```

### ansible.posix.sysctl

```yaml
- name: Set sysctl parameter
  ansible.posix.sysctl:
    name: net.ipv4.ip_forward
    value: '1'
    state: present
    reload: true
```

---

## Secrets management lookups

### HashiCorp Vault

```yaml
# Requires: ansible-galaxy collection install community.hashi_vault
# Requires: pip install hvac

- name: Get database password from Vault
  ansible.builtin.set_fact:
    db_password: "{{ lookup('community.hashi_vault.hashi_vault', 'secret/data/database:password') }}"
  no_log: true
```

### AWS Secrets Manager

```yaml
# Requires: ansible-galaxy collection install community.aws
# Requires: pip install boto3 botocore

- name: Get credentials from Secrets Manager
  ansible.builtin.set_fact:
    db_creds: "{{ lookup('community.aws.aws_secret', 'prod/database/credentials', region='us-east-1') | from_json }}"
  no_log: true
```

### Azure Key Vault

```yaml
# Requires: ansible-galaxy collection install azure.azcollection

- name: Get secret from Key Vault
  ansible.builtin.set_fact:
    app_secret: "{{ lookup('azure.azcollection.azure_keyvault_secret', 'app-secret', vault_url='https://myvault.vault.azure.net') }}"
  no_log: true
```
