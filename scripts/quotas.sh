#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"
"$DIR/check-session.sh" >/dev/null

OUT="$DIR/../docs/evidence/quotas"
mkdir -p "$OUT"
# Instance types M2 might use; each is probed with a dry-run that creates nothing.
TYPES="t2.micro t3.micro t3.small t3.medium t2.medium m5.large c5.large"
SUBNET_EXPORT=kv-network-PrivateSubnet1Id
AMI_PARAM=/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64

# A denial is a result: its text is saved in place of the quota JSON.
for code in ec2 vpc cloudformation; do
  aws service-quotas list-service-quotas --service-code "$code" --region "$AWS_REGION" --output json \
    >"$OUT/$code.json" 2>&1 || echo "saved failure for $code" >&2
done

AMI=$(aws ssm get-parameter --name "$AMI_PARAM" --region "$AWS_REGION" --query Parameter.Value --output text 2>/dev/null || true)
if [ -z "$AMI" ]; then
  AMI=$(aws ec2 describe-images --owners amazon --filters 'Name=name,Values=al2023-ami-2023*-x86_64' --region "$AWS_REGION" \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
fi
SUBNET=$(aws cloudformation list-exports --region "$AWS_REGION" \
  --query "Exports[?Name=='$SUBNET_EXPORT'].Value" --output text)

{
  echo "region=$AWS_REGION ami=$AMI subnet=$SUBNET"
  for t in $TYPES; do
    msg=$(aws ec2 run-instances --dry-run --region "$AWS_REGION" --image-id "$AMI" --instance-type "$t" \
      --subnet-id "$SUBNET" --count 1 2>&1 || true)
    case "$msg" in
      *DryRunOperation*) echo "$t: allowed (DryRunOperation)" ;;
      *UnauthorizedOperation*) echo "$t: denied (UnauthorizedOperation)" ;;
      *) code=$(echo "$msg" | sed -n 's/.*(\([A-Za-z]*\)).*/\1/p' | head -1); echo "$t: other (${code:-unknown})" ;;
    esac
    echo "  $msg" | sed 's#\(assumed-role/[^/]*\)/[^ ]*#\1/<session>#' | tr -d '\r'
  done
} >"$OUT/instance-types.txt"
cat "$OUT/instance-types.txt"
