#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"

[ $# -ge 1 ] && [ -n "$1" ] || { echo "Usage: $0 <Owner>" >&2; exit 1; }
OWNER=$1
STACK=kv-network
"$DIR/check-session.sh" >/dev/null

# A stack that failed on first create cannot be updated, only deleted.
STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || true)
if [ "$STATUS" = ROLLBACK_COMPLETE ]; then
  aws cloudformation delete-stack --stack-name "$STACK" --region "$AWS_REGION"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
fi

aws cloudformation deploy --region "$AWS_REGION" --stack-name "$STACK" \
  --template-file "$DIR/../infra/network.yaml" \
  --parameter-overrides Owner="$OWNER" \
  --tags Project=capstone-kv Milestone=m1 Owner="$OWNER"
