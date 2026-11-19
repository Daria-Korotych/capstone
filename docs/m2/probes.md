# M2 sandbox probes

Probe stack `kv-probe` (t3.micro, kv-network public subnet), 2026-11-19. Deleted afterwards.

| Probe | Question | Result | Evidence | Consequence for the plan |
| --- | --- | --- | --- | --- |
| P1 | CloudFormation resolves the SSM AMI parameter; instance gets a public IP | ✅ | [p1-public-ip-ssm-ami.txt](evidence/probes/p1-public-ip-ssm-ami.txt) | Use `{{resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64}}` and `NetworkInterfaces` with `AssociatePublicIpAddress: true` |
| P2 | Changing the launch template (new `Tag`) replaces the instance | ✅ | [p2-replacement.txt](evidence/probes/p2-replacement.txt) | Plain `AWS::EC2::Instance` + `LaunchTemplate` Version `!GetAtt LT.LatestVersionNumber`; no ASG needed |
| P3 | Instance pulls a public GHCR image | ✅ | [p3-ghcr-pull.txt](evidence/probes/p3-ghcr-pull.txt) | Pull images from GHCR in UserData; no ECR |
| P4 | SSH via EC2 Instance Connect, no stored key | ✅ | [p4-ssh-instance-connect.txt](evidence/probes/p4-ssh-instance-connect.txt) | `ec2-instance-connect:SendSSHPublicKey` is allowed; SG port 22 from own /32 only |
| P5 | `AWS::EC2::KeyPair` + SSM private key | n/a (P4 passed) | none | Not needed |

- ASG fallback not probed: P2 replaced the instance.
- SSM Agent logs `instance management role is not configured`: do not plan on Session Manager.
- Need a fresh `send-ssh-public-key` before each SSH (key valid 60 s).
