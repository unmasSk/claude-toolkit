# Ansible Module Alternatives and FQCN Migration

## Quick detection

Use the FQCN checker script to find non-FQCN module usage automatically:

```bash
bash scripts/check_fqcn.sh playbook.yml
bash scripts/check_fqcn.sh roles/webserver/
bash scripts/check_fqcn.sh .
```

---

## Why FQCN matters

- Explicitly shows which collection provides the module
- Prevents naming conflicts when multiple collections are installed
- Prevents breakage when modules move between collections between Ansible releases
- Required by `ansible-lint --profile production`

---

## Deprecated modules and replacements

### Package management

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `apt` | `ansible.builtin.apt` | Use FQCN |
| `yum` | `ansible.builtin.dnf` | dnf preferred for RHEL 8+ |
| `pip` | `ansible.builtin.pip` | Use FQCN |
| `easy_install` | `ansible.builtin.pip` | easy_install removed in Python 3.12 |
| `homebrew` | `community.general.homebrew` | Moved to community.general |
| `zypper` | `community.general.zypper` | Moved to community.general |
| `apk` | `community.general.apk` | Moved to community.general |

### File operations

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `copy` | `ansible.builtin.copy` | Use FQCN |
| `file` | `ansible.builtin.file` | Use FQCN |
| `template` | `ansible.builtin.template` | Use FQCN |
| `lineinfile` | `ansible.builtin.lineinfile` | Use FQCN |
| `blockinfile` | `ansible.builtin.blockinfile` | Use FQCN |
| `synchronize` | `ansible.posix.synchronize` | Moved to ansible.posix |
| `acl` | `ansible.posix.acl` | Moved to ansible.posix |

### Service management

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `service` | `ansible.builtin.service` or `ansible.builtin.systemd` | Use systemd for systemd-based systems |
| `systemd` | `ansible.builtin.systemd` | Use FQCN |

### User and group management

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `user` | `ansible.builtin.user` | Use FQCN |
| `group` | `ansible.builtin.group` | Use FQCN |
| `authorized_key` | `ansible.posix.authorized_key` | Moved to ansible.posix |

### Networking

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `get_url` | `ansible.builtin.get_url` | Use FQCN |
| `uri` | `ansible.builtin.uri` | Use FQCN |
| `iptables` | `ansible.builtin.iptables` | Use FQCN |
| `ufw` | `community.general.ufw` | Moved to community.general |
| `firewalld` | `ansible.posix.firewalld` | Moved to ansible.posix |

### Command execution

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `command` | `ansible.builtin.command` | Use FQCN; prefer specific modules |
| `shell` | `ansible.builtin.shell` | Use FQCN; prefer specific modules |
| `raw` | `ansible.builtin.raw` | Use FQCN; only when no Python on target |
| `script` | `ansible.builtin.script` | Use FQCN |

### Cloud providers

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `ec2` | `amazon.aws.ec2_instance` | Use amazon.aws collection |
| `ec2_ami` | `amazon.aws.ec2_ami` | Use amazon.aws collection |
| `ec2_vpc` | `amazon.aws.ec2_vpc_net` | Use amazon.aws collection |
| `azure_rm_*` | `azure.azcollection.*` | Use azure.azcollection |
| `gcp_*` | `google.cloud.*` | Use google.cloud collection |
| `docker_container` | `community.docker.docker_container` | Use community.docker |
| `docker_image` | `community.docker.docker_image` | Use community.docker |

### Database

| Deprecated | Replacement | Notes |
|-----------|-------------|-------|
| `mysql_db` | `community.mysql.mysql_db` | Use community.mysql |
| `mysql_user` | `community.mysql.mysql_user` | Use community.mysql |
| `postgresql_db` | `community.postgresql.postgresql_db` | Use community.postgresql |
| `postgresql_user` | `community.postgresql.postgresql_user` | Use community.postgresql |
| `mongodb_*` | `community.mongodb.*` | Use community.mongodb |

---

## Migration examples

```yaml
# Before
- name: Install nginx
  apt:
    name: nginx
    state: present

# After
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present
```

```yaml
# Before
- name: Configure firewall
  ufw:
    rule: allow
    port: '443'

# After
- name: Configure firewall
  community.general.ufw:
    rule: allow
    port: '443'
```

---

## Installing required collections

```bash
ansible-galaxy collection install ansible.posix
ansible-galaxy collection install community.general
ansible-galaxy collection install community.docker
ansible-galaxy collection install community.mysql
ansible-galaxy collection install community.postgresql
ansible-galaxy collection install amazon.aws
ansible-galaxy collection install azure.azcollection
ansible-galaxy collection install google.cloud
```

Or pin versions in `requirements.yml`:

```yaml
---
collections:
  - name: ansible.posix
    version: ">=1.5.0"
  - name: community.general
    version: ">=6.0.0"
  - name: community.docker
    version: ">=3.0.0"
  - name: community.mysql
    version: ">=3.0.0"
  - name: community.postgresql
    version: ">=2.0.0"
```

```bash
ansible-galaxy collection install -r requirements.yml
```

---

## Checking for deprecated modules

```bash
# Lint with production profile (includes deprecated module rules)
ansible-lint --profile production playbook.yml

# Show available rules related to deprecated modules
ansible-lint -L | grep deprecated
```

---

## Version compatibility notes

| Ansible version | Change |
|----------------|--------|
| 2.9 | Last version with many modules in ansible.builtin |
| 2.10+ | Collections separated from core |
| 2.12+ | Many deprecated modules removed from core |
| 2.14+ | FQCN strongly recommended; ansible-lint enforces it |
