# Terraform Security Checklist

## Secrets management

### Detection

```bash
grep -rE "(password|secret|api_key|access_key)\s*=\s*\"[^$]" *.tf
grep -rE "private_key\s*=\s*\"" *.tf
grep -rE "token\s*=\s*\"[^$]" *.tf
```

### Insecure

```hcl
resource "aws_db_instance" "example" {
  username = "admin"
  password = "hardcoded_password123"  # Never do this
}
```

### Secure

```hcl
variable "db_password" {
  type      = string
  sensitive = true
}

resource "aws_db_instance" "example" {
  username = "admin"
  password = var.db_password
}

# Better: fetch from Secrets Manager
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "prod/database/password"
}

resource "aws_db_instance" "example" {
  password = jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"]
}
```

Mark sensitive outputs:

```hcl
output "db_password" {
  value     = aws_db_instance.example.password
  sensitive = true
}
```

---

## Network security

### Overly permissive security groups

```hcl
# Bad: SSH open to world
ingress {
  from_port   = 22
  to_port     = 22
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

# Good: restricted to specific CIDR
variable "admin_cidr" {
  type = string
}

resource "aws_security_group" "app" {
  ingress {
    description = "SSH from admin network only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
}
```

### Public S3 buckets

```hcl
# Always block public access
resource "aws_s3_bucket_public_access_block" "example" {
  bucket                  = aws_s3_bucket.example.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

---

## Encryption

### Encryption at rest

Resources to check: RDS, S3, EBS, DynamoDB, Elasticsearch, Kinesis, SQS.

```hcl
# RDS
resource "aws_db_instance" "example" {
  storage_encrypted = true
  kms_key_id        = aws_kms_key.db.arn
}

# S3
resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}

# EBS
resource "aws_instance" "web" {
  root_block_device {
    encrypted  = true
    kms_key_id = aws_kms_key.data.arn
    volume_type = "gp3"
  }
}
```

### Encryption in transit

```hcl
# ALB HTTPS with TLS 1.2+
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.example.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.cert.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.example.arn
  }
}

# Redirect HTTP to HTTPS
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.example.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```

---

## IAM security

### Least privilege

```hcl
# Bad: admin wildcard
{
  "Effect": "Allow",
  "Action": "*",
  "Resource": "*"
}

# Good: specific actions scoped to specific resources
data "aws_iam_policy_document" "s3_read_only" {
  statement {
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.app_data.arn,
      "${aws_s3_bucket.app_data.arn}/*"
    ]
  }
}
```

### MFA requirement

```hcl
data "aws_iam_policy_document" "require_mfa" {
  statement {
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]
    condition {
      test     = "BoolIfExists"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["false"]
    }
  }
}
```

### Cross-account access

```hcl
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::123456789012:root"]
    }
    actions = ["sts:AssumeRole"]
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }
  }
}
```

---

## Logging and monitoring

```hcl
# CloudTrail
resource "aws_cloudtrail" "main" {
  name                          = "main-trail"
  s3_bucket_name               = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail        = true
  enable_logging               = true
  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }
}

# VPC Flow Logs
resource "aws_flow_log" "vpc" {
  vpc_id          = aws_vpc.main.id
  traffic_type    = "ALL"
  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_cloudwatch_log_group.flow_logs.arn
}

# Encrypted CloudWatch log group
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/app/logs"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn
}
```

---

## Resource-specific checklists

### RDS

- [ ] `storage_encrypted = true`
- [ ] `publicly_accessible = false`
- [ ] `backup_retention_period` > 0
- [ ] Multi-AZ for production
- [ ] `deletion_protection = true`

### ElastiCache

- [ ] `at_rest_encryption_enabled = true`
- [ ] `transit_encryption_enabled = true`
- [ ] Auth token enabled for Redis
- [ ] Subnet group in private subnets

### Lambda

- [ ] Environment variables encrypted with KMS
- [ ] VPC config if accessing private resources
- [ ] IAM role follows least-privilege
- [ ] Dead letter queue configured

### ECS/EKS

- [ ] Secrets managed via Secrets Manager (not env vars)
- [ ] Container images scanned
- [ ] RBAC configured

---

## State file security

### Terraform 1.11+ (S3 native locking)

```hcl
terraform {
  backend "s3" {
    bucket       = "terraform-state-bucket"
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    kms_key_id   = "arn:aws:kms:..."
    use_lockfile = true
  }
}
```

### Terraform < 1.11 (DynamoDB locking)

```hcl
terraform {
  backend "s3" {
    bucket         = "terraform-state-bucket"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:..."
    dynamodb_table = "terraform-locks"
  }
}
```

State checklist:
- [ ] Encryption enabled
- [ ] State locking configured
- [ ] Versioning enabled on state bucket
- [ ] Access restricted via IAM
- [ ] State files never committed to version control

---

## Automated security scanning

### Trivy (recommended — unified scanner)

> **Warning:** Trivy v0.60.0 has known regression issues causing panics when scanning Terraform. Use v0.59.x or v0.61.0+ if affected.

```bash
# Install
brew install trivy

# Scan Terraform directory
trivy config ./terraform

# High and critical only
trivy config --severity HIGH,CRITICAL ./terraform

# JSON output for CI
trivy config -f json -o results.json ./terraform

# Scan Terraform plan (more accurate — resolves variables)
terraform show -json tfplan > tfplan.json
trivy config tfplan.json

# Use tfvars for variable resolution
trivy config --tf-vars prod.terraform.tfvars ./terraform
```

Inline suppression:

```hcl
# trivy:ignore:AVD-AWS-0086
resource "aws_s3_bucket" "example" {
  bucket = "my-bucket"
}
```

### Checkov 3.0

```bash
# Basic scan
checkov -d .

# Deep analysis with Terraform plan
terraform plan -out=tf.plan
terraform show -json tf.plan > tfplan.json
checkov -f tfplan.json --deep-analysis

# Create baseline (ignore existing issues)
checkov -d . --create-baseline

# Run against baseline (only new issues)
checkov -d . --baseline .checkov.baseline

# Skip specific checks
checkov -d . --skip-check CKV_AWS_20,CKV_AWS_21
```

Checkov 3.0 improvements over 2.x:
- Deep analysis mode fully resolves `for_each`, dynamic blocks
- Baseline feature to track only new issues
- 36 new operators including `SUBSET` and `jsonpath_*`

### Tool comparison

| Tool | Policy language | Built-in policies | Best for |
|------|----------------|-------------------|----------|
| trivy | Rego | 1000+ | All-in-one scanning (containers + IaC) |
| checkov | Python/YAML | 3000+ | Multi-framework, compliance, deep analysis |

Note: tfsec is deprecated and merged into Trivy. Terrascan was archived in November 2025. Use Trivy or Checkov for new projects.

---

## Quick security audit commands

```bash
# Hardcoded secrets
grep -r "password\s*=\s*\"" . --include="*.tf"
grep -r "secret\s*=\s*\"" . --include="*.tf"

# Open security groups
grep -r "0.0.0.0/0" . --include="*.tf"

# Unencrypted resources
grep -r "encrypted\s*=\s*false" . --include="*.tf"

# Missing backup config
grep -r "backup_retention_period\s*=\s*0" . --include="*.tf"
```
