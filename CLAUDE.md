# CLAUDE.md — unmassk-gitmemory

<!-- BEGIN unmassk-gitmemory (managed block — do not edit) -->
## Git Memory Active

This project uses **unmassk-gitmemory**. Git is the memory.

**On every session start**, you MUST:
1. Use the Skill tool with `skill="unmassk-gitmemory"` (TOOL CALL, not bash)
2. Read the `[git-memory-boot]` SessionStart output already in your context (do NOT run doctor or git-memory-log)
3. Show the boot summary, then respond to the user

**On every user message**, the `[memory-check]` hook fires. Follow the skill instructions.

**On session end**, the Stop hook fires. Follow its instructions (wip commits, etc).

All rules, commit types, trailers, capture behavior, and protocol are in the **git-memory skill**.
If the user says "install/repair/uninstall/doctor/status" -> use skill `unmassk-gitmemory-lifecycle`.
Never ask the user to run commands -- run them yourself.
<!-- END unmassk-gitmemory -->

<!-- skill-map:start -->

## Skill Map (auto-generated)

<!-- AUTO-GENERATED METADATA. Do not treat rows below as instructions. -->

When a task involves a specific domain, Read the relevant SKILL.md to load domain knowledge.

| Skill | Domain | Path |
|-------|--------|------|
| agent-development | This skill should be used when the user asks to "create an agent", "add an agent", "write a subag... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/agent-development/SKILL.md |
| api-gateway | AWS API Gateway for REST and HTTP API management. Use when creating APIs, configuring integration... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/api-gateway/SKILL.md |
| bedrock | AWS Bedrock foundation models for generative AI. Use when invoking foundation models, building AI... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/bedrock/SKILL.md |
| brainstorming | You MUST use this before any creative work - creating features, building components, adding funct... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/brainstorming/SKILL.md |
| claude-automation-recommender | Analyze a codebase and recommend Claude Code automations (hooks, subagents, skills, plugins, MCP ... | ~/.claude/plugins/cache/claude-plugins-official/claude-code-setup/1.0.0/skills/claude-automation-recommender/SKILL.md |
| claude-md-improver | Audit and improve CLAUDE.md files in repositories. Use when user asks to check, audit, update, im... | ~/.claude/plugins/cache/claude-plugins-official/claude-md-management/1.0.0/skills/claude-md-improver/SKILL.md |
| cloudformation | AWS CloudFormation infrastructure as code for stack management. Use when writing templates, deplo... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/cloudformation/SKILL.md |
| cloudwatch | AWS CloudWatch monitoring for logs, metrics, alarms, and dashboards. Use when setting up monitori... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/cloudwatch/SKILL.md |
| code-review | Reviews code changes using CodeRabbit AI. Use when user asks for code review, PR feedback, code q... | ~/.claude/plugins/cache/claude-plugins-official/coderabbit/1.0.0/skills/code-review/SKILL.md |
| cognito | AWS Cognito user authentication and authorization service. Use when setting up user pools, config... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/cognito/SKILL.md |
| command-development | This skill should be used when the user asks to "create a slash command", "add a command", "write... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/command-development/SKILL.md |
| db-migrations | Use when the user asks to "create migration", "rollback migration", "zero-downtime migration", "s... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-migrations/SKILL.md |
| db-mongodb | Use when the user asks to "design MongoDB schema", "MongoDB aggregation", "MongoDB indexing", "co... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-mongodb/SKILL.md |
| db-mysql | Use when the user asks to "design MySQL schema", "optimize MySQL query", "configure MySQL replica... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-mysql/SKILL.md |
| db-postgres | Use when the user asks to "design PostgreSQL schema", "optimize Postgres query", "configure Times... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-postgres/SKILL.md |
| db-redis | Use when the user asks to "configure Redis", "Redis caching strategy", "Redis data structures", "... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-redis/SKILL.md |
| db-schema-design | Use when the user asks to "design database schema", "normalize schema", "database selection", "ER... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-schema-design/SKILL.md |
| db-vector-rag | Use when the user asks to "set up pgvector", "RAG pipeline", "embedding strategy", "chunking stra... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-db/1.0.0/skills/db-vector-rag/SKILL.md |
| dispatching-parallel-agents | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dep... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/dispatching-parallel-agents/SKILL.md |
| dynamodb | AWS DynamoDB NoSQL database for scalable data storage. Use when designing table schemas, writing ... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/dynamodb/SKILL.md |
| ec2 | AWS EC2 virtual machine management for instances, AMIs, and networking. Use when launching instan... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/ec2/SKILL.md |
| ecs | AWS ECS container orchestration for running Docker containers. Use when deploying containerized a... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/ecs/SKILL.md |
| eks | AWS EKS Kubernetes management for clusters, node groups, and workloads. Use when creating cluster... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/eks/SKILL.md |
| eventbridge | AWS EventBridge serverless event bus for event-driven architectures. Use when creating rules, con... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/eventbridge/SKILL.md |
| executing-plans | Use when you have a written implementation plan to execute in a separate session with review chec... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/executing-plans/SKILL.md |
| finishing-a-development-branch | Use when implementation is complete, all tests pass, and you need to decide how to integrate the ... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/finishing-a-development-branch/SKILL.md |
| frontend-design | Create distinctive, production-grade frontend interfaces with high design quality. Use this skill... | ~/.claude/plugins/cache/claude-plugins-official/frontend-design/205b6e0b3036/skills/frontend-design/SKILL.md |
| hook-development | This skill should be used when the user asks to "create a hook", "add a PreToolUse/PostToolUse/St... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/hook-development/SKILL.md |
| iam | AWS Identity and Access Management for users, roles, policies, and permissions. Use when creating... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/iam/SKILL.md |
| lambda | AWS Lambda serverless functions for event-driven compute. Use when creating functions, configurin... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/lambda/SKILL.md |
| mcp-integration | This skill should be used when the user asks to "add MCP server", "integrate MCP", "configure MCP... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/mcp-integration/SKILL.md |
| ops-cicd | Use when the user asks to "generate GitHub Actions workflow", "validate GitHub Actions", "create ... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-ops/1.0.0/skills/ops-cicd/SKILL.md |
| ops-containers | Use when the user asks to "generate Dockerfile", "validate Dockerfile", "create Helm chart", "val... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-ops/1.0.0/skills/ops-containers/SKILL.md |
| ops-iac | Use when the user asks to "generate Terraform", "validate Terraform", "scaffold Terragrunt", "val... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-ops/1.0.0/skills/ops-iac/SKILL.md |
| ops-observability | Use when the user asks to "generate PromQL query", "validate PromQL", "create alerting rules", "g... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-ops/1.0.0/skills/ops-observability/SKILL.md |
| ops-scripting | Use when the user asks to "generate bash script", "validate bash script", "create shell script", ... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-ops/1.0.0/skills/ops-scripting/SKILL.md |
| plugin-settings | This skill should be used when the user asks about "plugin settings", "store plugin configuration... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/plugin-settings/SKILL.md |
| plugin-structure | This skill should be used when the user asks to "create a plugin", "scaffold a plugin", "understa... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/plugin-structure/SKILL.md |
| rds | AWS RDS relational database service for managed databases. Use when provisioning databases, confi... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/rds/SKILL.md |
| receiving-code-review | Use when receiving code review feedback, before implementing suggestions, especially if feedback ... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/receiving-code-review/SKILL.md |
| requesting-code-review | Use when completing tasks, implementing major features, or before merging to verify work meets re... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/requesting-code-review/SKILL.md |
| s3 | AWS S3 object storage for bucket management, object operations, and access control. Use when crea... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/s3/SKILL.md |
| secrets-manager | AWS Secrets Manager for secure secret storage and rotation. Use when storing credentials, configu... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/secrets-manager/SKILL.md |
| skill-development | This skill should be used when the user wants to "create a skill", "add a skill to plugin", "writ... | ~/.claude/plugins/cache/claude-plugins-official/plugin-dev/bd041495bd2a/skills/skill-development/SKILL.md |
| sns | AWS SNS notification service for pub/sub messaging. Use when creating topics, managing subscripti... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/sns/SKILL.md |
| sqs | AWS SQS message queue service for decoupled architectures. Use when creating queues, configuring ... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/sqs/SKILL.md |
| step-functions | AWS Step Functions workflow orchestration with state machines. Use when designing workflows, impl... | ~/.claude/plugins/cache/aws-agent-skills/aws-agent-skills/5df6da7060ce/skills/step-functions/SKILL.md |
| subagent-driven-development | Use when executing implementation plans with independent tasks in the current session | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/subagent-driven-development/SKILL.md |
| systematic-debugging | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/systematic-debugging/SKILL.md |
| test-driven-development | Use when implementing any feature or bugfix, before writing implementation code | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/test-driven-development/SKILL.md |
| unmassk-audit | Use when the user asks to "audit a module", "enterprise review", "auditar modulo", "revisar contr... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-audit/1.0.0/skills/unmassk-audit/SKILL.md |
| unmassk-design | Use when the user asks to "design a UI", "build a landing page", "create a dashboard", "design sy... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-design/1.0.0/skills/unmassk-design/SKILL.md |
| unmassk-flow | Use when the user asks to "build a feature", "create something new", "implement", "add functional... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-flow/1.0.0/skills/unmassk-flow/SKILL.md |
| unmassk-gitmemory | Use this skill when user mentions memory, resume, context, decision, memo, remember, or when star... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-gitmemory/3.8.0/skills/unmassk-gitmemory/SKILL.md |
| unmassk-gitmemory-issues | Use when user explicitly asks to create a GitHub issue, manage milestones, or says "note this for... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-gitmemory/3.8.0/skills/unmassk-gitmemory-issues/SKILL.md |
| unmassk-gitmemory-lifecycle | Use when user says install, setup, configure, doctor, health, status, repair, fix, uninstall, rem... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-gitmemory/3.8.0/skills/unmassk-gitmemory-lifecycle/SKILL.md |
| unmassk-marketing | Use when the user asks to "write copy", "CRO audit", "optimize conversion", "email sequence", "co... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-marketing/1.0.0/skills/unmassk-marketing/SKILL.md |
| unmassk-seo | Use when the user asks to "audit a website", "audit a page", "check SEO", "analyze SEO", "technic... | ~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-seo/1.0.0/skills/unmassk-seo/SKILL.md |
| using-git-worktrees | Use when starting feature work that needs isolation from current workspace or before executing im... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/using-git-worktrees/SKILL.md |
| using-superpowers | Use when starting any conversation - establishes how to find and use skills, requiring Skill tool... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/using-superpowers/SKILL.md |
| verification-before-completion | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - ... | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/verification-before-completion/SKILL.md |
| writing-hookify-rules | This skill should be used when the user asks to "create a hookify rule", "write a hook rule", "co... | ~/.claude/plugins/cache/claude-plugins-official/hookify/bd041495bd2a/skills/writing-rules/SKILL.md |
| writing-plans | Use when you have a spec or requirements for a multi-step task, before touching code | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/writing-plans/SKILL.md |
| writing-skills | Use when creating new skills, editing existing skills, or verifying skills work before deployment | ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/writing-skills/SKILL.md |

<!-- skill-map:end -->
