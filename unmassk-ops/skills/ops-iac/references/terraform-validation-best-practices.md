# Terraform Validation Best Practices

## Project structure

### Recommended directory layout

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   └── production/
├── modules/
│   ├── networking/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   ├── compute/
│   └── database/
└── global/
    ├── iam/
    └── route53/
```

Split files when a single file exceeds 200 lines or when resource groups are logically distinct (e.g., `networking.tf`, `compute.tf`).

---

## Variable best practices

### Always include description, type, and validation

```hcl
variable "instance_type" {
  description = "EC2 instance type for web servers"
  type        = string
  default     = "t3.micro"

  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
    error_message = "Instance type must be t3.micro, t3.small, or t3.medium."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}
```

### Use typed variables

```hcl
variable "instance_count" { type = number }
variable "enable_monitoring" { type = bool }
variable "availability_zones" { type = list(string) }
variable "tags" { type = map(string) }

variable "database_config" {
  type = object({
    engine            = string
    engine_version    = string
    instance_class    = string
    allocated_storage = number
  })
}
```

### Environment-specific values in .tfvars

```hcl
# environments/dev/terraform.tfvars
environment    = "dev"
instance_type  = "t3.micro"
instance_count = 1
enable_backup  = false

# environments/production/terraform.tfvars
environment    = "production"
instance_type  = "t3.large"
instance_count = 3
enable_backup  = true
```

---

## Module best practices

### Single responsibility

```hcl
# Good: focused module
module "vpc" {
  source = "./modules/vpc"
}

# Avoid: everything in one module
module "infrastructure" {
  source = "./modules/everything"
}
```

### Required vs optional variables

```hcl
# modules/database/variables.tf

# Required — no default
variable "database_name" {
  description = "Name of the database"
  type        = string
}

# Optional — sensible default
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}
```

### Output everything useful

```hcl
# modules/vpc/outputs.tf

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}
```

---

## State management blocks (prefer declarative over CLI)

### import block (1.5+)

Bring existing resources under Terraform management without manual `terraform import`:

```hcl
import {
  to = aws_vpc.main
  id = "vpc-0123456789abcdef0"
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = { Name = "main-vpc" }
}
```

Dynamic import (1.6+):

```hcl
import {
  to = aws_s3_bucket.logs
  id = "${var.environment}-logs-bucket"
}
```

Generate configuration automatically:

```bash
terraform plan -generate-config-out=generated.tf
```

Workflow:
1. Add `import` block
2. `terraform plan` to preview
3. Add or generate resource block
4. `terraform apply` to import
5. Remove `import` block after success

### moved block (1.1+)

Rename resources or reorganize modules without state surgery:

```hcl
# Rename
moved {
  from = aws_instance.web
  to   = aws_instance.web_server
}

# Move into a module
moved {
  from = aws_vpc.main
  to   = module.networking.aws_vpc.main
}

# Count to for_each migration
moved {
  from = aws_instance.web[0]
  to   = aws_instance.web["web-1"]
}
```

Keep `moved` blocks until all environments have applied.

### removed block (1.7+)

Stop managing a resource without destroying it:

```hcl
removed {
  from = aws_instance.legacy_server
  lifecycle {
    destroy = false
  }
}

# Or destroy it
removed {
  from = aws_s3_bucket.old_logs
  lifecycle {
    destroy = true
  }
}
```

### Block comparison

| Block | Version | Use case |
|-------|---------|----------|
| `import` | 1.5+ | Adopt existing infrastructure |
| `moved` | 1.1+ | Rename/restructure without state surgery |
| `removed` | 1.7+ | Stop managing without destroying |

---

## Code quality

### Use locals for computed values

```hcl
locals {
  name_prefix   = "${var.environment}-${var.project}"
  is_production = var.environment == "production"
  instance_type = local.is_production ? "t3.large" : "t3.micro"

  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
```

### count vs for_each

```hcl
# for_each for map-like resources (stable when items are added/removed)
locals {
  subnets = {
    public_a  = { cidr = "10.0.1.0/24", az = "us-east-1a" }
    private_a = { cidr = "10.0.3.0/24", az = "us-east-1a" }
  }
}

resource "aws_subnet" "main" {
  for_each          = local.subnets
  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az
  tags = { Name = each.key }
}

# count for simple on/off conditionals
resource "aws_kms_key" "encryption" {
  count       = var.enable_encryption ? 1 : 0
  description = "Encryption key"
}

# Access with try() to handle missing items
kms_master_key_id = try(aws_kms_key.encryption[0].arn, null)
```

### Dynamic blocks

Use only when the number of blocks is variable. They reduce readability.

```hcl
resource "aws_security_group" "example" {
  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

---

## Validation workflow

```bash
# 1. Format check
terraform fmt -check -recursive

# 2. Validate configuration (no network calls)
terraform validate

# 3. Plan (requires credentials)
terraform plan

# 4. Security scan
checkov -d .
# or
trivy config ./terraform

# 5. Compliance testing
terraform-compliance -p terraform.plan -f compliance/
```

### Pre-commit hooks

`.pre-commit-config.yaml`:

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

### CI/CD pipeline

```yaml
# .github/workflows/terraform.yml
name: Terraform

on: [pull_request]

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: hashicorp/setup-terraform@v2

      - name: Format check
        run: terraform fmt -check -recursive

      - name: Init
        run: terraform init

      - name: Validate
        run: terraform validate

      - name: Plan
        run: terraform plan
```

---

## Security

Never commit these files:

```
# .gitignore
.terraform/
*.tfstate
*.tfstate.backup
*.tfvars
.terraform.lock.hcl
```

Rules:
- Use `sensitive = true` for sensitive variables and outputs
- Encrypt remote state with KMS
- Use least-privilege IAM for the Terraform executor
- Pin provider and module versions

---

## Performance

```bash
# Targeted plan for large configs
terraform plan -target=module.vpc

# Parallel operations
terraform apply -parallelism=20

# Provider plugin cache
# ~/.terraformrc
plugin_cache_dir = "$HOME/.terraform.d/plugin-cache"
```

Cache data source results in locals to avoid redundant API calls:

```hcl
data "aws_ami" "ubuntu" {
  most_recent = true
  # ... filters
}

locals {
  ami_id = data.aws_ami.ubuntu.id
}

resource "aws_instance" "web" {
  count         = 10
  ami           = local.ami_id  # Reuse, don't repeat the data source
  instance_type = var.instance_type
}
```

---

## Documentation

Generate module documentation with terraform-docs:

```bash
terraform-docs markdown table . > README.md
```

Inline comments for non-obvious decisions:

```hcl
# DNS hostnames required for Route53 private hosted zones
resource "aws_vpc" "main" {
  enable_dns_hostnames = true
  enable_dns_support   = true
}
```
