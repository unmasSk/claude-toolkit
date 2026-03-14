# Terraform Best Practices

## Project structure

### Standard single-root layout

```
terraform-project/
├── main.tf              # Primary resource definitions
├── variables.tf         # Input variable declarations
├── outputs.tf           # Output value declarations
├── versions.tf          # Terraform and provider version constraints
├── backend.tf           # Backend configuration
├── locals.tf            # Local values (optional)
├── data.tf              # Data source definitions (optional)
├── terraform.tfvars     # Variable values (gitignored if sensitive)
└── modules/             # Local modules
    └── networking/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

### Multi-environment layout

```
terraform-project/
├── modules/
│   └── vpc/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   └── production/
└── shared/
```

Split files when a single file exceeds ~200 lines, or by logical group (e.g., `networking.tf`, `compute.tf`).

---

## Naming conventions

### Resources

Use `snake_case`. Be descriptive; avoid redundant prefixes.

```hcl
# Good
resource "aws_instance" "web_server" {}
resource "aws_security_group" "web_server_sg" {}

# Avoid
resource "aws_instance" "aws_instance_web" {}
resource "aws_security_group" "sg" {}
```

### Variables

```hcl
# Good
variable "instance_count" {}
variable "backup_retention_days" {}
variable "enable_encryption" {}

# Avoid
variable "count" {}
variable "retention" {}
variable "encrypt" {}
```

### Modules

Directory names use kebab-case; module call references use snake_case.

```hcl
# Directory: modules/vpc-networking/
module "vpc_networking" {
  source = "./modules/vpc-networking"
}
```

### Tags

Use a consistent local block for all resources:

```hcl
locals {
  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Owner       = var.owner_email
    CostCenter  = var.cost_center
  }
}

resource "aws_instance" "web" {
  tags = merge(local.common_tags, {
    Name = "${var.environment}-web-server"
    Role = "webserver"
  })
}
```

---

## Version pinning

### Terraform version

```hcl
terraform {
  required_version = ">= 1.10, < 2.0"
}
```

Feature version gates:
- `>= 1.11` — when write-only arguments (`*_wo`) are used
- `>= 1.10` — when ephemeral resources/variables are used
- `>= 1.14` — when `action` blocks or `list` resources are used
- Otherwise — follow the repository baseline (commonly `>= 1.8, < 2.0`)

### Provider versions

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.5.1"
    }
  }
}
```

Prefer `~>` (major-version pinning) for cloud providers. Avoid hardcoding "latest".

### Module versions

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.0"  # Always pin
}
```

---

## State management

### Remote backend (S3 — Terraform 1.11+)

```hcl
terraform {
  backend "s3" {
    bucket       = "my-terraform-state"
    key          = "project/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true       # S3-native locking (recommended for 1.11+)
    kms_key_id   = "alias/terraform-state"
  }
}
```

For Terraform < 1.11, use DynamoDB locking:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "project/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
    kms_key_id     = "alias/terraform-state"
  }
}
```

Always encrypt state. Always use state locking. Separate state files per environment and component.

---

## Variable management

### Variable declarations

Always include `description`, `type`, and validation where applicable.

```hcl
variable "instance_type" {
  description = "EC2 instance type for web servers"
  type        = string
  default     = "t3.micro"

  validation {
    condition     = can(regex("^t[23]\\.", var.instance_type))
    error_message = "Instance type must be from t2 or t3 family."
  }
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least 2 availability zones required."
  }
}

variable "database_password" {
  description = "Password for database admin user"
  type        = string
  sensitive   = true  # Prevents display in logs and plan output
}
```

### Variable precedence (high to low)

1. `-var` and `-var-file` command-line flags
2. `*.auto.tfvars` files (alphabetical order)
3. `terraform.tfvars.json`
4. `terraform.tfvars`
5. Environment variables (`TF_VAR_name`)
6. Default values in variable declarations

---

## Resource management

### Dependencies

```hcl
# Implicit dependency (preferred)
resource "aws_eip" "example" {
  instance = aws_instance.web.id
}

# Explicit dependency (when needed)
resource "aws_instance" "web" {
  depends_on = [
    aws_iam_role_policy.example
  ]
}
```

### Lifecycle rules

```hcl
resource "aws_instance" "web" {
  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
    ignore_changes = [
      tags["LastModified"],
      user_data,
    ]
  }
}
```

### count vs for_each

Prefer `for_each` for map-like resources — stable across changes:

```hcl
# for_each (preferred for named resources)
locals {
  subnets = {
    public_a  = { cidr = "10.0.1.0/24", az = "us-east-1a" }
    private_a = { cidr = "10.0.3.0/24", az = "us-east-1a" }
  }
}

resource "aws_subnet" "main" {
  for_each = local.subnets
  cidr_block        = each.value.cidr
  availability_zone = each.value.az
}

# count (for simple conditionals)
resource "aws_cloudwatch_log_group" "app" {
  count = var.enable_logging ? 1 : 0
  name  = "/aws/app/logs"
}
```

---

## Locals

```hcl
locals {
  az_count      = length(data.aws_availability_zones.available.names)
  instance_type = var.environment == "production" ? "t3.large" : "t3.micro"

  subnet_cidrs = {
    for idx, az in data.aws_availability_zones.available.names :
    az => cidrsubnet(var.vpc_cidr, 8, idx)
  }
}
```

---

## Dynamic blocks

```hcl
resource "aws_security_group" "web" {
  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      description = ingress.value.description
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

Use dynamic blocks sparingly. They reduce readability.

---

## Data sources

```hcl
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
}
```

---

## Module design

### Module structure

```
module/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
└── examples/
    └── complete/
        └── main.tf
```

Each module has one clear responsibility. Output everything a caller might need.

```hcl
# outputs.tf
output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "List of IDs of private subnets"
  value       = aws_subnet.private[*].id
}
```

---

## State management blocks (declarative, prefer over CLI)

### import (1.5+)

```hcl
import {
  to = aws_vpc.main
  id = "vpc-0123456789abcdef0"
}
```

Generate config for imported resources:

```bash
terraform plan -generate-config-out=generated.tf
```

### moved (1.1+)

Rename or move resources without manual state manipulation:

```hcl
moved {
  from = aws_instance.web
  to   = aws_instance.web_server
}
```

Keep `moved` blocks until all environments have applied.

### removed (1.7+)

Stop managing a resource without destroying it:

```hcl
removed {
  from = aws_instance.legacy_server
  lifecycle {
    destroy = false
  }
}
```

---

## Security

- Never hardcode secrets in `.tf` files
- Mark sensitive variables with `sensitive = true`
- Mark sensitive outputs with `sensitive = true`
- Never commit `.tfstate`, `.tfstate.backup`, or `.tfvars` files with secrets
- Use least-privilege IAM for the Terraform executor
- Enable encryption and MFA on state buckets
- Pin provider and module versions to prevent supply-chain surprises

`.gitignore`:

```
.terraform/
*.tfstate
*.tfstate.backup
*.tfvars
.terraform.lock.hcl
```

---

## Testing and validation

```bash
terraform fmt -check -recursive
terraform validate
terraform plan
```

Pre-commit hooks (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.83.0
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
      - id: terraform_docs
      - id: terraform_tflint
```

---

## Performance

- Use targeted plans for large configs: `terraform plan -target=module.vpc`
- Split large configurations into separate state files
- Use `-parallelism` flag: `terraform apply -parallelism=20`
- Cache provider plugins:

```
# ~/.terraformrc
plugin_cache_dir = "$HOME/.terraform.d/plugin-cache"
```

---

## Common pitfalls

1. Hardcoding values — use variables and data sources
2. Not pinning versions — always pin provider and module versions
3. Editing state files manually — never
4. Circular dependencies — structure resources properly
5. Not using remote state for teams
6. No state locking — always configure
7. Missing input validation — use `validation` blocks
8. Not tagging resources — tag for cost tracking and compliance
