# Terraform Advanced Features (1.10+)

Modern Terraform features for enhanced infrastructure management.

## Feature version matrix

| Feature | Version | Status |
|---------|---------|--------|
| Ephemeral resources / variables / outputs | 1.10+ | GA |
| Write-only arguments (`*_wo`) | 1.11+ | GA |
| S3 native state locking (`use_lockfile`) | 1.11+ | GA |
| Actions blocks | 1.14+ | GA (Nov 2025) |
| List resources / `terraform query` | 1.14+ | GA (Nov 2025) |

---

## Ephemeral values and write-only arguments (1.10+)

**Purpose:** Manage secrets (passwords, tokens) without storing them in Terraform state, plan files, or logs.

### Ephemeral resources

Ephemeral resources generate temporary values that exist only during a Terraform operation and are never persisted.

```hcl
# Generate a temporary password — NOT stored in state
ephemeral "random_password" "db_password" {
  length           = 16
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store in Secrets Manager (only the secret ARN is in state, not the value)
resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id                = aws_secretsmanager_secret.db_password.id
  secret_string_wo         = ephemeral.random_password.db_password.result
  secret_string_wo_version = 1
}
```

### Write-only arguments (1.11+)

Arguments ending in `_wo` accept values but never store them in state:

```hcl
ephemeral "random_password" "db_password" {
  length = 16
}

resource "aws_db_instance" "example" {
  instance_class      = "db.t3.micro"
  allocated_storage   = "5"
  engine              = "postgres"
  username            = "admin"
  skip_final_snapshot = true

  # password_wo is never stored in state or plan
  password_wo         = ephemeral.random_password.db_password.result
  password_wo_version = 1  # Increment this to trigger a password rotation
}
```

### Ephemeral variables and outputs

```hcl
variable "api_token" {
  type      = string
  sensitive = true
  ephemeral = true  # Not stored in state
}

output "generated_password" {
  value     = ephemeral.random_password.main.result
  ephemeral = true  # Not stored in state
}
```

### Key concepts

| Concept | Version | Behavior |
|---------|---------|----------|
| `ephemeral` block | 1.10+ | Resource never stored in state |
| Ephemeral variables | 1.10+ | `ephemeral = true` on variable |
| Ephemeral outputs | 1.10+ | `ephemeral = true` on output |
| Write-only arguments | 1.11+ | `*_wo` attributes, never in state |
| `*_wo_version` | 1.11+ | Version counter to trigger updates |
| `ephemeralasnull` | 1.10+ | Convert ephemeral value to null for conditionals |

### Behavior notes

- Ephemeral resources are recreated on every `terraform plan` (no state to compare against)
- Write-only arguments show as `(sensitive value)` in plan output
- Checkov may not fully detect issues in ephemeral resources (no state to inspect)
- Provider support required: AWS, Azure, GCP, Kubernetes, Random providers support ephemeral resources

---

## Actions blocks (1.14+)

**Purpose:** Execute provider-defined imperative operations (Lambda invocations, cache invalidations) that don't fit the standard CRUD lifecycle.

### Basic examples

```hcl
# Invoke a Lambda function
action "aws_lambda_invoke" "process_data" {
  config {
    function_name = aws_lambda_function.processor.function_name
    payload       = jsonencode({ action = "process" })
  }
}

# CloudFront cache invalidation
action "aws_cloudfront_create_invalidation" "invalidate_cache" {
  config {
    distribution_id = aws_cloudfront_distribution.cdn.id
    paths           = ["/*"]
  }
}
```

### Lifecycle-triggered actions

```hcl
resource "aws_s3_object" "data_file" {
  bucket       = aws_s3_bucket.data.id
  key          = "data/input.json"
  source       = "local/input.json"
  content_type = "application/json"

  lifecycle {
    action_trigger {
      events  = [after_update]
      actions = [action.aws_lambda_invoke.process_data]
    }
  }
}

action "aws_lambda_invoke" "process_data" {
  config {
    function_name = aws_lambda_function.processor.function_name
    payload = jsonencode({
      bucket = aws_s3_bucket.data.id
      key    = aws_s3_object.data_file.key
    })
  }
}
```

### CLI commands

```bash
# Trigger a specific action directly
terraform apply -invoke=action.aws_lambda_invoke.process_data

# Normal apply still triggers lifecycle-bound actions
terraform apply
```

### When to use actions

- Lambda/Cloud Function invocations
- CDN cache invalidation
- Database migrations
- Post-deployment API calls
- One-time operations with no resource creation

### Behavior notes

- Actions don't create resources in state
- Failed actions don't roll back completed actions
- Actions run in dependency order
- Lifecycle-triggered actions run automatically during apply

### Provider support (as of Nov 2025)

| Provider | Available actions |
|----------|------------------|
| AWS | `aws_lambda_invoke`, `aws_cloudfront_create_invalidation`, `aws_ec2_stop_instance` |
| Azure | Planned |
| GCP | Planned |

---

## List resources and terraform query (1.14+)

**Purpose:** Query and filter existing cloud infrastructure from within Terraform, without importing resources.

### Query file syntax

Query files use the `.tfquery.hcl` extension:

```hcl
# infrastructure_audit.tfquery.hcl

list "aws_s3_bucket" "production_buckets" {
  filter {
    tags = {
      Environment = "production"
    }
  }
}

list "aws_instance" "large_instances" {
  filter {
    instance_type = "t3.large"
  }
}

list "aws_vpc" "all_vpcs" {}
```

### Advanced queries

```hcl
# Find untagged resources
list "aws_s3_bucket" "untagged_buckets" {
  filter {
    tags = null
  }
}

# Find overly permissive security groups
list "aws_security_group" "public_ingress" {
  filter {
    ingress {
      cidr_blocks = ["0.0.0.0/0"]
    }
  }
}

# Find by name pattern
list "aws_instance" "web_servers" {
  filter {
    tags = {
      Name = "web-*"
    }
  }
}
```

### CLI commands

```bash
# Execute query
terraform query

# Execute specific query file
terraform query -query=infrastructure_audit.tfquery.hcl

# Generate Terraform configuration for discovered resources
terraform query -generate-config-out=discovered.tf

# Validate query files
terraform validate -query
```

### Use cases

- Discover resources not managed by Terraform
- Compliance checks (find resources missing required tags)
- Cost analysis (find oversized or unused resources)
- Generate import configuration for manual resources
- Drift detection

### Behavior notes

- Queries require valid provider authentication and appropriate IAM permissions
- Large queries may be rate-limited by cloud providers
- Generated config from `-generate-config-out` must be reviewed before use
