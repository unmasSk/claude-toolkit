# Common Terraform Patterns

## Multi-environment pattern

### Directory structure

```
terraform/
├── modules/
│   └── app/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── environments/
    ├── dev/
    │   ├── main.tf
    │   ├── terraform.tfvars
    │   └── backend.tf
    ├── staging/
    └── production/
```

### Implementation

```hcl
# environments/dev/main.tf
module "app" {
  source = "../../modules/app"

  environment    = "dev"
  instance_type  = "t3.micro"
  instance_count = 1
  enable_backups = false
}

# environments/production/main.tf
module "app" {
  source = "../../modules/app"

  environment    = "production"
  instance_type  = "t3.large"
  instance_count = 3
  enable_backups = true
}
```

---

## Workspace pattern

Use workspaces when environment configurations are very similar and share the same module.

```hcl
locals {
  environment_config = {
    dev = {
      instance_type  = "t3.micro"
      instance_count = 1
      enable_backups = false
    }
    prod = {
      instance_type  = "t3.large"
      instance_count = 3
      enable_backups = true
    }
  }

  config = local.environment_config[terraform.workspace]
}

resource "aws_instance" "app" {
  count         = local.config.instance_count
  instance_type = local.config.instance_type
}
```

```bash
terraform workspace new dev
terraform workspace select dev
terraform apply
```

---

## Data layer separation pattern

Separate stateful (database, storage) from stateless (compute, networking) infrastructure into independent state files.

```
terraform/
├── data-layer/
│   ├── main.tf
│   ├── outputs.tf
│   └── backend.tf
└── app-layer/
    ├── main.tf
    ├── outputs.tf
    └── backend.tf
```

```hcl
# data-layer/main.tf
resource "aws_db_instance" "main" {
  deletion_protection = true
  skip_final_snapshot = false

  lifecycle {
    prevent_destroy = true
  }
}

# app-layer/main.tf
data "terraform_remote_state" "data_layer" {
  backend = "s3"
  config = {
    bucket = "terraform-state"
    key    = "data-layer/terraform.tfstate"
    region = "us-east-1"
  }
}

resource "aws_instance" "app" {
  user_data = templatefile("${path.module}/user_data.sh", {
    database_endpoint = data.terraform_remote_state.data_layer.outputs.database_endpoint
  })
}
```

---

## Module composition pattern

```hcl
module "network" {
  source = "./modules/network"
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  tags                 = local.common_tags
}

module "security" {
  source              = "./modules/security"
  vpc_id              = module.network.vpc_id
  allowed_cidr_blocks = var.allowed_cidr_blocks
  tags                = local.common_tags
}

module "compute" {
  source             = "./modules/compute"
  vpc_id             = module.network.vpc_id
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.security.app_security_group_id]
  instance_type      = var.instance_type
  instance_count     = var.instance_count
  tags               = local.common_tags
}

module "database" {
  source             = "./modules/database"
  vpc_id             = module.network.vpc_id
  subnet_ids         = module.network.database_subnet_ids
  security_group_ids = [module.security.db_security_group_id]
  master_password    = var.db_password
  tags               = local.common_tags
}
```

---

## Conditional resource creation pattern

```hcl
# count for simple conditionals
resource "aws_instance" "bastion" {
  count         = var.create_bastion ? 1 : 0
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.public[0].id
}

# for_each with conditional map
resource "aws_cloudwatch_log_group" "optional" {
  for_each          = var.enable_logging ? toset(var.log_group_names) : toset([])
  name              = each.value
  retention_in_days = var.log_retention_days
}

# Conditional module
module "cdn" {
  count  = var.enable_cdn ? 1 : 0
  source = "./modules/cdn"

  origin_domain_name = aws_lb.main.dns_name
}

# Access conditionally created resource
output "bastion_public_ip" {
  value = var.create_bastion ? aws_instance.bastion[0].public_ip : null
}
```

---

## Tagging strategy pattern

```hcl
locals {
  mandatory_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Owner       = var.owner_email
    CostCenter  = var.cost_center
  }

  common_tags = merge(local.mandatory_tags, var.additional_tags)

  database_tags = merge(local.common_tags, {
    Type      = "Database"
    Backup    = "Required"
    Retention = "30days"
  })

  compute_tags = merge(local.common_tags, {
    Type          = "Compute"
    PatchSchedule = "Sundays-2AM"
  })
}
```

---

## Secret injection pattern

```hcl
data "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = "${var.environment}/app/secrets"
}

locals {
  app_secrets = jsondecode(data.aws_secretsmanager_secret_version.app_secrets.secret_string)
}

# ECS task with secrets from Secrets Manager
resource "aws_ecs_task_definition" "app" {
  container_definitions = jsonencode([{
    name  = "app"
    image = var.app_image
    secrets = [
      {
        name      = "DB_PASSWORD"
        valueFrom = "${data.aws_secretsmanager_secret.app_secrets.arn}:password::"
      }
    ]
    environment = [
      {
        name  = "DB_HOST"
        value = aws_db_instance.main.endpoint
      }
    ]
  }])
}
```

---

## Auto-scaling pattern

```hcl
resource "aws_launch_template" "app" {
  name_prefix   = "${var.project_name}-"
  image_id      = data.aws_ami.app.id
  instance_type = var.instance_type

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.app.id]
  }

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    environment = var.environment
  }))
}

resource "aws_autoscaling_group" "app" {
  vpc_zone_identifier       = aws_subnet.private[*].id
  target_group_arns         = [aws_lb_target_group.app.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 300
  min_size                  = var.min_capacity
  max_size                  = var.max_capacity
  desired_capacity          = var.desired_capacity

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }
}

resource "aws_autoscaling_policy" "cpu_target" {
  name                   = "${var.project_name}-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

---

## Blue-green deployment pattern

```hcl
variable "active_environment" {
  type    = string
  default = "blue"
  validation {
    condition     = contains(["blue", "green"], var.active_environment)
    error_message = "Must be blue or green."
  }
}

module "blue" {
  source         = "./modules/environment"
  name           = "blue"
  instance_count = var.active_environment == "blue" ? var.desired_capacity : 1
  ami_id         = var.blue_ami_id
}

module "green" {
  source         = "./modules/environment"
  name           = "green"
  instance_count = var.active_environment == "green" ? var.desired_capacity : 1
  ami_id         = var.green_ami_id
}

resource "aws_lb_listener_rule" "weighted" {
  listener_arn = aws_lb_listener.main.arn
  action {
    type = "forward"
    forward {
      target_group {
        arn    = aws_lb_target_group.blue.arn
        weight = var.active_environment == "blue" ? 100 : 0
      }
      target_group {
        arn    = aws_lb_target_group.green.arn
        weight = var.active_environment == "green" ? 100 : 0
      }
    }
  }
  condition {
    path_pattern { values = ["/*"] }
  }
}
```

---

## Disaster recovery pattern

```hcl
provider "aws" {
  alias  = "primary"
  region = var.primary_region
}

provider "aws" {
  alias  = "dr"
  region = var.dr_region
}

module "primary" {
  source    = "./modules/infrastructure"
  providers = { aws = aws.primary }
  is_primary = true
}

module "dr" {
  source    = "./modules/infrastructure"
  providers = { aws = aws.dr }
  is_primary = false
}

resource "aws_route53_record" "primary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.example.com"
  type    = "A"
  set_identifier = "primary"
  failover_routing_policy { type = "PRIMARY" }
  alias {
    name                   = module.primary.load_balancer_dns
    zone_id               = module.primary.load_balancer_zone_id
    evaluate_target_health = true
  }
  health_check_id = aws_route53_health_check.primary.id
}

resource "aws_route53_record" "dr" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.example.com"
  type    = "A"
  set_identifier = "dr"
  failover_routing_policy { type = "SECONDARY" }
  alias {
    name                   = module.dr.load_balancer_dns
    zone_id               = module.dr.load_balancer_zone_id
    evaluate_target_health = true
  }
}
```

---

## Cost optimization patterns

```hcl
# Spot instances for non-critical workloads
resource "aws_autoscaling_group" "batch" {
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 1
      on_demand_percentage_above_base_capacity = 20
      spot_allocation_strategy                 = "capacity-optimized"
    }
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.batch.id
        version            = "$Latest"
      }
    }
  }
}

# Shutdown non-production environments overnight
resource "aws_autoscaling_schedule" "shutdown_evening" {
  count                  = var.environment != "production" ? 1 : 0
  scheduled_action_name  = "shutdown-evening"
  min_size               = 0
  max_size               = 0
  desired_capacity       = 0
  recurrence             = "0 20 * * *"
  autoscaling_group_name = aws_autoscaling_group.app.name
}

# S3 lifecycle to reduce storage costs
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "transition-old-data"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    expiration {
      days = 365
    }
  }
}

# Budget alert
resource "aws_budgets_budget" "monthly" {
  name         = "${var.project_name}-monthly-budget"
  budget_type  = "COST"
  limit_amount = var.monthly_budget
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
```
