# Common Terraform Errors

## Initialization errors

### Failed to query available provider packages

```
Error: Failed to query available provider packages

Could not retrieve the list of available versions for provider
hashicorp/aws: no available releases match the given constraints
```

Cause: invalid version constraint, network issue, or wrong provider source.

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"  # Verify source path
      version = "~> 5.0"         # Verify version exists
    }
  }
}
```

```bash
# Clear cache and reinitialize
rm -rf .terraform .terraform.lock.hcl
terraform init
```

### Module not installed

```
Error: Module not installed

This configuration requires module "vpc" but it is not installed.
```

```bash
terraform init         # Initial install
terraform init -upgrade  # Update modules
```

---

## Validation errors

### Unsupported argument

```
Error: Unsupported argument

An argument named "instance_class" is not expected here.
```

Cause: typo in argument name or argument not supported in this resource type.

```bash
terraform console
> provider::aws::schema::aws_instance
```

### Missing required argument

```
Error: Missing required argument

The argument "ami" is required, but no definition was found.
```

```hcl
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
}
```

### Incorrect attribute value type

```
Error: Incorrect attribute value type

Inappropriate value for attribute "instance_count": a number is required.
```

```hcl
variable "instance_count" {
  type    = number
  default = 1  # Not "1"
}

# Or convert explicitly
resource "aws_instance" "web" {
  count = tonumber(var.instance_count)
}
```

---

## Resource errors

### Resource already exists / quota exceeded

```
Error: Error creating VPC: VpcLimitExceeded
```

Import the existing resource or request a quota increase:

```bash
terraform import aws_vpc.main vpc-12345678

aws service-quotas request-service-quota-increase \
  --service-code vpc \
  --quota-code L-F678F1CE \
  --desired-value 10
```

### Resource not found

```
Error: Error reading VPC: VPCNotFound: The vpc ID 'vpc-12345' does not exist
```

```bash
# Refresh state
terraform refresh

# Remove from state if truly deleted
terraform state rm aws_vpc.main

# Check region configuration
provider "aws" {
  region = "us-east-1"
}
```

### Resource dependency violation

```
Error: Error deleting VPC: DependencyViolation
```

Destroy dependent resources first:

```bash
terraform destroy -target=aws_subnet.private
terraform destroy -target=aws_vpc.main
```

---

## State management errors

### State lock acquisition failed

```
Error: Error acquiring the state lock

Lock Info:
  ID:        abc123
  Operation: OperationTypeApply
```

Cause: another process holds the lock, or a previous run crashed without releasing it.

```bash
# Verify no other terraform process is running
ps aux | grep terraform

# Force unlock (use carefully — only when certain no other process is active)
terraform force-unlock abc123
```

### State file version mismatch

```
Error: state snapshot was created by Terraform v1.5.0, which is newer than current v1.4.0
```

```bash
# Install required Terraform version
tfenv install 1.5.0
tfenv use 1.5.0
```

### Backend configuration changed

```
Error: Backend configuration changed
```

```bash
terraform init -reconfigure
# or
terraform init -migrate-state
```

---

## Plan/apply errors

### Provider authentication failed

```
Error: no valid credential sources for Terraform AWS Provider found
```

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"

# Or use a named profile
export AWS_PROFILE="your-profile"

# Verify credentials
aws sts get-caller-identity
```

### Cycle dependency

```
Error: Cycle: aws_security_group.web, aws_security_group.db
```

Break the cycle by separating inline rules into `aws_security_group_rule` resources:

```hcl
resource "aws_security_group" "web" {
  name = "web-sg"
  # No inline ingress/egress rules
}

resource "aws_security_group" "db" {
  name = "db-sg"
}

resource "aws_security_group_rule" "web_to_db" {
  type                     = "egress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  security_group_id        = aws_security_group.web.id
  source_security_group_id = aws_security_group.db.id
}
```

### Invalid count argument

```
Error: Invalid count argument

The "count" value depends on resource attributes that cannot be determined until apply.
```

Use variables or locals instead of resource attributes for `count`:

```hcl
# Bad
resource "aws_instance" "web" {
  count = length(aws_subnet.private)  # Unknown at plan time
}

# Good — use for_each with known values
resource "aws_instance" "web" {
  for_each = toset(var.subnet_ids)
  subnet_id = each.value
}
```

### Invalid for_each argument

Same root cause as invalid count:

```hcl
# Use a local with known keys instead of resource attributes
locals {
  subnets = {
    private_a = { cidr = "10.0.1.0/24" }
    private_b = { cidr = "10.0.2.0/24" }
  }
}

resource "aws_subnet" "private" {
  for_each   = local.subnets
  cidr_block = each.value.cidr
}
```

---

## Variable errors

### No value for required variable

```
Error: No value for required variable

The root module input variable "db_password" is not set.
```

```bash
terraform apply -var="db_password=secretpass"
echo 'db_password = "secretpass"' > terraform.tfvars
export TF_VAR_db_password="secretpass"
```

### Invalid variable type

```
Error: Invalid value for input variable

The given value is not suitable for var.instance_count: number required.
```

```hcl
# In terraform.tfvars use the correct type
instance_count = 3  # Not "3"
```

---

## Module errors

### Unsuitable value for module variable

```
Error: Unsuitable value for var.vpc_cidr
```

Check types match the module's variable declaration:

```hcl
module "vpc" {
  vpc_cidr = "10.0.0.0/16"  # Must be a string, not an object
}
```

### Unsupported attribute in module output

```
Error: Unsupported attribute

This object does not have an attribute named "vpc_id".
```

Verify the output is defined in the module's `outputs.tf` and the name is spelled correctly.

---

## Provider-specific errors

### AWS: InvalidGroup.Duplicate

```
Error: Error creating Security Group: InvalidGroup.Duplicate
```

```bash
terraform import aws_security_group.web sg-12345678

# Or use data source for existing group
data "aws_security_group" "existing" {
  name = "web-sg"
}
```

### AWS: Timeout waiting for resource

```hcl
resource "aws_db_instance" "main" {
  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }
}
```

### AWS: UnauthorizedOperation

Check IAM permissions for the action being performed:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:user/terraform \
  --action-names ec2:RunInstances \
  --resource-arns "*"
```

---

## Workspace errors

### Workspace already exists

```bash
# Select instead of create
terraform workspace select production

# List available workspaces
terraform workspace list
```

---

## Formatting errors

```bash
# Auto-fix formatting
terraform fmt

# Check only (for CI)
terraform fmt -check -recursive
```

---

## Import errors

### Cannot import non-existent remote object

```bash
# Verify the resource exists in the cloud provider first
aws ec2 describe-instances --instance-ids i-12345

# Use correct resource address format
terraform import aws_instance.web i-1234567890abcdef0
```

---

## Debugging

```bash
# Enable debug logging
export TF_LOG=DEBUG
terraform apply

# Log to file
export TF_LOG_PATH="./terraform.log"

# Validate only (no network calls)
terraform validate

# Plan with verbose output
terraform plan -detailed-exitcode
```

---

## Prevention

```bash
# Run before every apply
terraform fmt -check -recursive
terraform validate
terraform plan

# Pre-commit hook script
#!/bin/bash
terraform fmt -check -recursive || exit 1
terraform validate || exit 1
```

Always use validation blocks in variable declarations to catch bad values early:

```hcl
variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}
```
