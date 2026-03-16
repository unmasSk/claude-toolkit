# Terragrunt Common Patterns

> Include syntax: use `find_in_parent_folders("root.hcl")` for all new projects. Only use `find_in_parent_folders()` (no argument) when the repo intentionally keeps a legacy root file named `terragrunt.hcl`.

---

## Root configuration patterns

### Single-account with S3 backend

```hcl
# root.hcl
remote_state {
  backend = "s3"
  config = {
    bucket       = "company-terraform-state"
    key          = "${path_relative_to_include()}/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true  # TF 1.11+; use dynamodb_table for older versions
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = var.region
}
EOF
}

inputs = {
  region = "us-east-1"
  common_tags = {
    ManagedBy = "Terragrunt"
  }
}
```

### Multi-account with role assumption

```hcl
# root.hcl
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))
  env_vars     = read_terragrunt_config(find_in_parent_folders("env.hcl"))

  account_id  = local.account_vars.locals.account_id
  region      = local.region_vars.locals.region
  environment = local.env_vars.locals.environment
}

remote_state {
  backend = "s3"
  config = {
    bucket       = "terraform-state-${local.account_id}"
    key          = "${path_relative_to_include()}/terraform.tfstate"
    region       = local.region
    encrypt      = true
    use_lockfile = true
    role_arn     = "arn:aws:iam::${local.account_id}:role/TerraformRole"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
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
    tags = {
      Environment = "${local.environment}"
      ManagedBy   = "Terragrunt"
    }
  }
}
EOF
}
```

---

## Child module patterns

### Standalone module (no dependencies)

```hcl
# environments/prod/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/vpc/aws?version=5.1.0"
}

inputs = {
  name = "prod-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = false
}
```

### Module with single dependency

```hcl
# environments/prod/rds/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/rds/aws?version=6.1.0"
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id                      = "vpc-mock123"
    database_subnet_group_name  = "mock-subnet-group"
    database_subnet_ids         = ["subnet-mock1", "subnet-mock2"]
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "destroy"]
}

dependency "security_group" {
  config_path = "../security-groups/database"

  mock_outputs = {
    security_group_id = "sg-mock123"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "destroy"]
}

inputs = {
  identifier        = "prod-db"
  engine            = "postgres"
  engine_version    = "14"
  instance_class    = "db.t3.small"
  allocated_storage = 20

  vpc_security_group_ids = [dependency.security_group.outputs.security_group_id]
  db_subnet_group_name   = dependency.vpc.outputs.database_subnet_group_name
}
```

### Module with multiple dependencies

```hcl
# environments/prod/eks/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/eks/aws?version=19.15.0"
}

dependencies {
  paths = ["../vpc", "../security-groups", "../iam-roles"]
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    private_subnet_ids = ["subnet-1", "subnet-2"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "security_groups" {
  config_path = "../security-groups"

  mock_outputs = {
    cluster_security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "iam" {
  config_path = "../iam-roles"

  mock_outputs = {
    cluster_role_arn = "arn:aws:iam::123456789012:role/mock-role"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  cluster_name    = "prod-eks"
  cluster_version = "1.28"

  vpc_id                    = dependency.vpc.outputs.vpc_id
  subnet_ids                = dependency.vpc.outputs.private_subnet_ids
  cluster_security_group_id = dependency.security_groups.outputs.cluster_security_group_id
  iam_role_arn              = dependency.iam.outputs.cluster_role_arn

  enable_irsa = true
}
```

### Module with environment-conditional inputs

```hcl
# catalog/units/app/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = get_env("ENVIRONMENT", "dev")

  instance_counts = {
    dev     = 1
    staging = 2
    prod    = 3
  }

  instance_types = {
    dev     = "t3.micro"
    staging = "t3.small"
    prod    = "t3.medium"
  }
}

terraform {
  source = "../../terraform-modules/app"
}

inputs = {
  environment    = local.env
  instance_count = local.instance_counts[local.env]
  instance_type  = local.instance_types[local.env]

  enable_monitoring = local.env == "prod"
  enable_backups    = local.env == "prod"

  tags = merge(
    { Environment = local.env, ManagedBy = "Terragrunt" },
    local.env == "prod" ? { CriticalResource = "true" } : {}
  )
}
```

---

## Environment file pattern

Separate environment variables into `_env/` files and symlink or copy to each environment dir:

```
infrastructure/
├── root.hcl
├── _env/
│   ├── prod.hcl
│   ├── staging.hcl
│   └── dev.hcl
├── prod/
│   ├── env.hcl         # Copy of ../_env/prod.hcl
│   └── vpc/
│       └── terragrunt.hcl
```

```hcl
# _env/prod.hcl
locals {
  environment   = "prod"
  region        = "us-east-1"
  vpc_cidr      = "10.0.0.0/16"
  instance_type = "t3.medium"
  min_size      = 3
  max_size      = 10
}
```

```hcl
# prod/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "tfr:///terraform-aws-modules/vpc/aws?version=5.1.0"
}

inputs = {
  name = "${local.env.locals.environment}-vpc"
  cidr = local.env.locals.vpc_cidr
  azs  = ["${local.env.locals.region}a", "${local.env.locals.region}b"]
}
```

---

## Advanced patterns

### Hooks for pre/post operations

```hcl
terraform {
  source = "tfr:///terraform-aws-modules/rds/aws?version=6.1.0"

  before_hook "validate_env" {
    commands = ["apply"]
    execute  = ["bash", "-c", "test -n \"$DB_PASSWORD\" || (echo 'DB_PASSWORD not set' && exit 1)"]
  }

  after_hook "notify_deployment" {
    commands     = ["apply"]
    execute      = ["bash", "-c", "echo 'Deployment complete'"]
    run_on_error = false
  }

  error_hook "log_error" {
    commands = ["apply", "plan"]
    execute  = ["bash", "-c", "echo 'Terraform operation failed'"]
  }
}
```

### External data integration

```hcl
locals {
  # Suppress Terragrunt banner output with --quiet
  git_branch = run_cmd("--quiet", "git", "rev-parse", "--abbrev-ref", "HEAD")
  account_id = run_cmd("--quiet", "aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text")
  config     = jsondecode(file("${get_terragrunt_dir()}/config.json"))
}

inputs = {
  git_branch = local.git_branch
  account_id = local.account_id
  app_name   = local.config.app_name
}
```

### Kubernetes provider from EKS outputs

```hcl
dependency "eks" {
  config_path = "../eks-cluster"

  mock_outputs = {
    cluster_endpoint    = "https://mock-endpoint"
    cluster_certificate = "mock-cert"
    cluster_name        = "mock-cluster"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

generate "kubernetes_provider" {
  path      = "kubernetes_provider.tf"
  if_exists = "overwrite"
  contents  = <<EOF
provider "kubernetes" {
  host                   = "${dependency.eks.outputs.cluster_endpoint}"
  cluster_ca_certificate = base64decode("${dependency.eks.outputs.cluster_certificate}")

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", "${dependency.eks.outputs.cluster_name}"]
  }
}
EOF
}
```

---

## Stacks (0.78+)

Stacks define infrastructure blueprints that generate unit configurations programmatically.

```hcl
# terragrunt.stack.hcl
locals {
  environment = "prod"
  region      = "us-east-1"
  units_path  = find_in_parent_folders("catalog/units")
}

unit "vpc" {
  source = "${local.units_path}/vpc"
  path   = "vpc"
  values = {
    name        = "${local.environment}-vpc"
    cidr        = "10.0.0.0/16"
    aws_region  = local.region
    environment = local.environment
  }
}

unit "database" {
  source = "${local.units_path}/database"
  path   = "database"
  values = {
    name        = "${local.environment}-db"
    engine      = "postgres"
    vpc_path    = "../vpc"
    environment = local.environment
  }
}
```

Catalog unit reads `values.*` directly:

```hcl
# catalog/units/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/vpc/aws?version=5.1.0"
}

inputs = {
  name               = values.name
  cidr               = values.cidr
  azs                = ["${values.aws_region}a", "${values.aws_region}b"]
  enable_nat_gateway = try(values.enable_nat, true)
  tags = { Environment = values.environment, ManagedBy = "Terragrunt" }
}
```

Stack commands:

```bash
terragrunt stack generate       # Generate unit configs from stack definition
terragrunt stack run plan       # Plan all units
terragrunt stack run apply      # Apply all units
terragrunt stack output         # Aggregated outputs from all units
terragrunt stack clean          # Remove generated directories
```

For versioned unit definitions from a remote repo:

```hcl
unit "vpc" {
  source = "git::git@github.com:acme/infrastructure-catalog.git//units/vpc?ref=v1.0.0"
  path   = "vpc"
  values = { name = "main", cidr = "10.0.0.0/16" }
}
```

---

## Feature flags

```hcl
feature "enable_monitoring" {
  default = false
}

inputs = {
  enable_monitoring = feature.enable_monitoring.value
}
```

```bash
# Override via CLI
terragrunt apply --feature enable_monitoring=true

# Override via environment variable
TG_FEATURE="enable_monitoring=true" terragrunt apply
```

Feature flags for module versioning:

```hcl
feature "module_version" {
  default = "v1.0.0"
}

terraform {
  source = "git::git@github.com:acme/modules.git//vpc?ref=${feature.module_version.value}"
}
```

Feature flags with conditional logic:

```hcl
feature "enable_ha" {
  default = false
}

locals {
  instance_count = feature.enable_ha.value ? 3 : 1
  instance_type  = feature.enable_ha.value ? "t3.medium" : "t3.micro"
}
```

---

## Exclude blocks

The `exclude` block replaces the deprecated `skip` attribute.

```hcl
# Exclude a unit from apply and destroy, allow plan
exclude {
  if      = true
  actions = ["apply", "destroy"]
}

# Exclude all actions except output
exclude {
  if      = true
  actions = ["all_except_output"]
}

# Environment-based exclusion with feature flag
feature "prod" {
  default = false
}

exclude {
  if      = !feature.prod.value
  actions = ["all_except_output"]
}
```

```bash
# Enable production deployment
terragrunt run --all apply --feature prod=true
```

---

## Errors blocks

The `errors` block replaces deprecated `retryable_errors`, `retry_max_attempts`, and `retry_sleep_interval_sec`.

```hcl
errors {
  retry "transient_errors" {
    retryable_errors = [
      "(?s).*Failed to load state.*tcp.*timeout.*",
      "(?s).*Error installing provider.*TLS handshake timeout.*",
      "(?s).*429 Too Many Requests.*",
    ]
    max_attempts       = 3
    sleep_interval_sec = 5
  }

  ignore "known_warnings" {
    ignorable_errors = [
      ".*Warning: Resource already exists.*",
      "!.*Error: critical.*"  # Negation: do NOT ignore critical errors
    ]
    message = "Ignoring known safe warnings"
  }
}
```

---

## OpenTofu engine

```hcl
# Use OpenTofu instead of Terraform
engine {
  source  = "github.com/gruntwork-io/terragrunt-engine-opentofu"
  version = "v0.0.15"
}

# Auto-install specific OpenTofu version
engine {
  source = "github.com/gruntwork-io/terragrunt-engine-opentofu"
  meta = {
    tofu_version     = "v1.9.1"
    tofu_install_dir = "/opt/tofu"
  }
}
```

---

## Provider cache

```bash
# Enable provider cache for run --all
terragrunt run --all plan --provider-cache

# Via environment variable
TG_PROVIDER_CACHE=1 terragrunt run --all apply

# Custom cache directory
TG_PROVIDER_CACHE=1 TG_PROVIDER_CACHE_DIR=/custom/cache terragrunt plan

# Shared cache server (for team/CI)
TG_PROVIDER_CACHE=1 \
TG_PROVIDER_CACHE_HOST=192.168.0.100 \
TG_PROVIDER_CACHE_PORT=5758 \
TG_PROVIDER_CACHE_TOKEN=my-secret \
terragrunt apply
```
