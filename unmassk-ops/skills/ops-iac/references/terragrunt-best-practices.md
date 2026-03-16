# Terragrunt Best Practices

## Version compatibility

| Feature | Minimum version |
|---------|----------------|
| `run --all` (replaces `run-all`) | 0.93+ |
| `hcl fmt` (replaces `hclfmt`) | 0.93+ |
| `hcl validate --inputs` (replaces `validate-inputs`) | 0.93+ |
| `dag graph` (replaces `graph-dependencies`) | 0.93+ |
| Stacks (GA) | 0.78+ |
| `errors` block (replaces `retryable_errors`) | 0.67+ |
| `exclude` block (replaces `skip`) | 0.67+ |
| Feature flags | 0.67+ |
| OpenTofu engine | 0.56+ |

Specify minimum version in root config:

```hcl
terragrunt_version_constraint = ">= 0.93.0"
terraform_version_constraint  = ">= 1.6.0, < 2.0.0"
```

---

## Directory structure

```
infrastructure/
├── root.hcl                # Root config (0.93+: name root.hcl, not terragrunt.hcl)
├── _env/
│   ├── prod.hcl
│   ├── staging.hcl
│   └── dev.hcl
├── prod/
│   ├── env.hcl             # Symlink or copy of ../_env/prod.hcl
│   ├── vpc/
│   │   └── terragrunt.hcl
│   ├── database/
│   │   └── terragrunt.hcl
│   └── app/
│       └── terragrunt.hcl
└── staging/
    └── ... (same structure)
```

Avoid flat structures without environment separation and avoid deeply nested paths beyond environment/module.

---

## DRY configuration

### Root config with remote state

```hcl
# root.hcl
remote_state {
  backend = "s3"
  config = {
    bucket     = "company-terraform-state-${local.account_id}"
    key        = "${path_relative_to_include()}/terraform.tfstate"
    region     = local.region
    encrypt    = true
    use_lockfile = true  # TF 1.11+ native S3 locking — no DynamoDB needed
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}
```

For Terraform < 1.11, use `dynamodb_table` instead of `use_lockfile`.

### Shared variables via read_terragrunt_config

```hcl
# common.hcl
locals {
  region      = "us-east-1"
  environment = "prod"
  common_tags = {
    Environment = local.environment
    ManagedBy   = "Terragrunt"
  }
}

# child terragrunt.hcl
locals {
  common = read_terragrunt_config(find_in_parent_folders("common.hcl"))
}

inputs = {
  region = local.common.locals.region
  tags   = local.common.locals.common_tags
}
```

### Include root config

```hcl
# child terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}
```

Use named includes (`include "root" {}`) — positional `include {}` is deprecated.

---

## Provider generation

Generate providers from root to avoid duplicating them in every module:

```hcl
# root.hcl
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))
  account_id   = local.account_vars.locals.account_id
  region       = local.region_vars.locals.region
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.region}"

  assume_role {
    role_arn = "arn:aws:iam::${local.account_id}:role/TerraformRole"
  }

  default_tags {
    tags = ${jsonencode(local.tags)}
  }
}
EOF
}

generate "versions" {
  path      = "versions.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
EOF
}
```

---

## Dependencies

Use explicit `dependency` blocks — not `data "terraform_remote_state"` — so Terragrunt can resolve the dependency graph automatically.

```hcl
dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id     = "vpc-mock123"
    subnet_ids = ["subnet-mock1", "subnet-mock2"]
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  mock_outputs_merge_strategy_with_state  = "shallow"
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnet_ids
}
```

Always provide `mock_outputs` — without them, `plan` and `validate` require the dependency to be deployed first.

When multiple unrelated dependencies exist, use a `dependencies` block to declare them without consuming outputs:

```hcl
dependencies {
  paths = ["../vpc", "../security-groups", "../iam-roles"]
}
```

---

## Inputs

Derive inputs from locals, dependency outputs, and functions. Never hardcode values that differ by environment or account.

```hcl
locals {
  region     = get_env("AWS_REGION", "us-east-1")
  account_id = get_aws_account_id()
}

inputs = {
  region     = local.region
  account_id = local.account_id

  # Override from environment variable with fallback
  instance_count = get_env("INSTANCE_COUNT", 3)

  # Optional config with fallback
  instance_type = try(local.env_config.locals.instance_type, "t3.micro")

  tags = merge(local.common_tags, { Module = "app" })
}
```

---

## Security

### State encryption

```hcl
remote_state {
  backend = "s3"
  config = {
    encrypt      = true
    kms_key_id   = "arn:aws:kms:us-east-1:123456789012:key/..."
    use_lockfile = true
  }
}
```

### IAM role assumption

```hcl
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  assume_role {
    role_arn = "arn:aws:iam::${local.account_id}:role/TerraformRole"
  }
}
EOF
}
```

### Secrets from environment only

```hcl
inputs = {
  database_password = get_env("DB_PASSWORD")  # Never hardcode
}
```

---

## Validation workflow

```bash
# Format check
terragrunt hcl fmt --check

# Validate inputs against module variables (0.93+)
terragrunt hcl validate --inputs

# Initialize
terragrunt init

# Validate Terraform config
terragrunt validate

# Plan
terragrunt plan
```

### Multi-module operations (0.93+)

```bash
# Validate all modules
terragrunt run --all validate

# Plan all modules
terragrunt run --all plan

# Apply all modules
terragrunt run --all apply

# Strict mode: errors on deprecated features
terragrunt --strict-mode run --all plan
# or
TG_STRICT_MODE=true terragrunt run --all plan
```

---

## Performance

```bash
# Parallel operations
terragrunt run --all apply --parallelism 4

# Provider cache for run --all
terragrunt run --all plan --provider-cache

# Via environment variable
TG_PROVIDER_CACHE=1 terragrunt run --all apply
```

Use `mock_outputs_merge_strategy_with_state = "shallow"` on dependencies to avoid fetching full output sets.

---

## Troubleshooting

### Circular dependency

Symptom: `Cycle detected in dependency graph`

Separate tightly-coupled resources into a single module or replace dependency outputs with data sources where no deployment ordering is needed.

### State lock error

Symptom: `Error acquiring the state lock`

```bash
terragrunt force-unlock <LOCK_ID>
```

### Module not found after source change

```bash
rm -rf .terragrunt-cache
terragrunt init
```
