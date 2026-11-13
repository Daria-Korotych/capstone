# AI architecture critique (M1)

Source: a separate AI session with read-only access to the repository, 2026-11-12. Input: `infra/network.yaml`, `infra/iam.yaml`, the four ADRs, `docs/budget.md`, `docs/labrole.md`, `docs/sandbox.md`, `scripts/deploy-network.sh`, `scripts/recreate.sh`. The transcript below is verbatim.

## Transcript

```text
Read both templates, the four ADRs, budget, labrole, sandbox docs and the deploy/recreate scripts. Here's the
  critique.

  Next action: add a free S3 gateway endpoint to the private route table in infra/network.yaml, then rewrite
  docs/budget.md to include how M2 instances get egress and how clients reach the system. Without those two, M2
  can't be deployed or used, and the budget doesn't hold.

  Fix now, most serious first

  1. The private subnets are a dead end for M2 (blocker)
  - infra/network.yaml:119: private subnets have only the local route. There's no NAT and no endpoints.
  - The budget (docs/budget.md) puts all 3 M2 instances in private subnets. Those instances can't install
    packages or reach S3, which M3 needs for the replication log. They can't reach SSM either, and without SSM
    or a public IP nobody can get onto them to operate them.
  - You also can't create an instance profile (iam:CreateRole is denied), so SSM wouldn't work even with
    endpoints. That holds unless the sandbox's own instance profile, listed in docs/sandbox.md, has SSM
    permissions. You haven't checked that.
  - ADR-0004 calls this "a decision for M2". It isn't something to defer: it decides where nodes go and what the
    budget is.
  - Change:
    - Add AWS::EC2::VPCEndpoint (S3, Gateway) on PrivateRouteTable now. It's free and you'll need it.
    - Check what the sandbox instance profile allows.
    - Then decide: a pre-built AMI plus the S3 endpoint, or a NAT that only exists during sessions. Write an ADR
      for it.

  2. The budget leaves out the expensive items (high)
  - The $28.60 / $7.69 figures are only EC2, EBS and CloudWatch.
  - Missing: NAT Gateway (about $0.045/h, roughly $33/month around the clock, already over the $20 ceiling),
    interface endpoints (about $0.01/h per endpoint per AZ, and SSM needs 3 endpoints × 2 AZs) and an ALB (about
    $0.0225/h plus LCU charges). These are approximate us-east-1 rates; confirm them in the same price-list
    files you already use.
  - Nothing says how clients reach the coordinator. A coordinator in a private subnet needs an ALB or a public
    node, and neither one is costed.
  - The session-mode estimate assumes EBS volumes survive between sessions, but docs/sandbox.md says persistence
    is still unknown.
  - Change: draw the client → coordinator → shard path, cost every piece of it, and assume the stacks are
    deleted at the end of each session.
  - Also, the project calls itself "serverless", yet the plan is 3 EC2 instances in a VPC. Pick one and justify
    it in an ADR. It's the first question an examiner will ask.

  3. ADR-0001 (ABAC) can't be built in this environment, and it will break kv-app (high)
  - You proved that iam:CreatePolicy and iam:CreateRole are denied. ADR-0001 still says the roles will live in
    kv-app.
  - That puts the same failure inside the app stack. Its whole create will roll back, which is exactly why
    ADR-0003 split IAM into kv-iam.
  - ABAC adds little here anyway. The ADR itself says the coordinator sets the tenant tag, so the coordinator is
    the real trust boundary.
  - Change:
    - Keep IAM resources out of kv-app.
    - Amend ADR-0001: for the sandbox, isolation is enforced by the coordinator with one prefix per tenant, plus
      cross-tenant tests. ABAC is the target for a real account.
    - Prefer one prefix per tenant over one bucket per tenant: no bucket provisioning step, and no bucket quota.

  4. The Environment parameter claims something the template doesn't do (medium)
  - network.yaml and iam.yaml accept Environment, but these are all hard-coded or not environment-aware:
    - the CIDR 10.20.0.0/16;
    - STACK=kv-network in scripts/deploy-network.sh;
    - the export names;
    - the IAM scope stack/kv-*/* (iam.yaml:215), so a kv-dev-readonly role can read every kv-* stack.
  - ADR-0004 says "another environment uses 10.30.0.0/16", but the template can't express that.
  - Change: delete the parameter, since the sandbox has one environment. If you keep it, make the CIDR and the
    IAM scope depend on it.

  5. "Read-only" in iam.yaml still exposes secrets (medium)
  - ec2:Describe* includes DescribeInstanceAttribute, which returns instance user data.
  - cloudformation:Get* includes GetTemplate.
  - Any secret you put in user data or in template defaults in M2 becomes readable by the reviewer role.
  - The deploy attempt trusted arn:aws:iam::…:root, which means any principal in the account with
    sts:AssumeRole. That isn't "only the supplied principal" as the docs claim.
  - Change:
    - Add an explicit Deny on ec2:DescribeInstanceAttribute, or adopt a written rule: no secrets in user data.
    - Trust a specific role ARN.
    - Set MaxSessionDuration: 3600.

  Later

  1. MapPublicIpOnLaunch: true on the public subnets gives every instance a paid, publicly reachable address,
     even ones launched there by mistake. Set it to false and assign public IPs explicitly.
  2. Tag duplication: the 5 tags repeated on every resource duplicate the stack-level --tags that
     deploy-network.sh already passes, and CloudFormation copies those to resources. Keep only Name per
     resource, and add Environment to --tags. Milestone: m1 will be wrong from M2 onward; drop it.
  3. No protection on the network stack:
     - aws cloudformation deploy runs its change set immediately. Use --no-execute-changeset when you want to
       review first.
     - Add a stack policy that denies Update:Replace on Vpc and the subnets, so a CIDR edit can't silently
       rebuild the network.
  4. recreate.sh only works because nothing imports the exports yet. Once kv-app exists, the delete will fail.
     Change the script to delete kv-app first, or accept that the R7 proof only applies to M1.
  5. Security hygiene: add VPC Flow Logs (to S3, which is cheap) and remove the default security group's
     allow-all rules. Also, AZs are chosen by name, not AZ ID. In us-east-1, use1-az3 has limited instance
     types, so pin by AZ ID, or at least check that t3.micro is offered in both chosen AZs.

  What holds up: separate stacks connected by exports, CloudFormation over Terraform (the state can't be lost
  when a session ends), /24 subnets with a CIDR that won't collide with common defaults, and evidence that is
  unusually thorough and honest.

  This was a read-only review: I didn't run cfn-lint or call AWS, the prices quoted are approximate, and I
  skimmed quotas.md, network.md and the openspec specs rather than reading them closely. The README has
  uncommitted changes.
```

## Моя позиція

- **Пункт 2 («serverless» проти 3 EC2) — не згодна**, бо курс сам вимагає coordinator node.

- **Пункт 3 (ABAC з ADR-0001 у пісочниці не збудувати) — згодна**, бо `iam:CreateRole` заборонено.
