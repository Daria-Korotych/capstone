#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"

ROLE=$("$DIR/check-session.sh")
ACCOUNT=$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)

DOC="$DIR/../docs/sandbox.md"
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EVIDENCE="$DIR/../docs/evidence/sandbox/${STAMP//:/}.txt"
mkdir -p "$(dirname "$EVIDENCE")"

if REGIONS=$(aws ec2 describe-regions --region us-east-1 --query 'Regions[].RegionName' --output text 2>/dev/null); then
  REGIONS=$(echo $REGIONS | tr ' ' '\n' | sort | tr '\n' ' ')
else
  REGIONS="us-east-1 us-east-2 us-west-1 us-west-2 eu-central-1 eu-north-1"
fi

REGION_LINES=""
for r in $REGIONS; do
  if err=$(aws ec2 describe-vpcs --region "$r" --max-items 1 --cli-connect-timeout 5 2>&1 >/dev/null); then
    result=allowed
  else
    code=$(echo "$err" | sed -n 's/.*An error occurred (\([A-Za-z]*\)).*/\1/p' | head -n 1)
    result="denied (${code:-unknown})"
  fi
  REGION_LINES="${REGION_LINES}- ${r}: ${result}"$'\n'
done

if out=$(aws cloudformation describe-stacks --stack-name kv-network --region "$AWS_REGION" --query 'Stacks[0].[StackStatus,CreationTime]' --output text 2>&1); then
  PERSIST="kv-network present (${out%%$'\t'*}, created ${out#*$'\t'})"
elif echo "$out" | grep -q 'does not exist'; then
  PERSIST="kv-network absent"
else
  code=$(echo "$out" | sed -n 's/.*An error occurred (\([A-Za-z]*\)).*/\1/p' | head -n 1)
  PERSIST="kv-network unknown (${code:-unknown})"
fi

{
  echo "Role: $ROLE"
  echo "Account: $ACCOUNT"
  echo "Identity: arn:aws:sts::${ACCOUNT}:assumed-role/${ROLE}/<session>"
  echo "Regions:"
  printf '%s' "$REGION_LINES"
  echo "Persistence: $PERSIST"
} > "$EVIDENCE"

{
  echo
  echo "## Run $STAMP"
  echo
  echo "- Role: $ROLE"
  echo "- Account: $ACCOUNT"
  echo "- Regions:"
  printf '%s' "$REGION_LINES" | sed 's/^/  /'
  echo "- Persistence: $PERSIST"
  echo "- Evidence: docs/evidence/sandbox/$(basename "$EVIDENCE")"
} >> "$DOC"

echo "Appended run to docs/sandbox.md"
