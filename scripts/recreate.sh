#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"

[ $# -ge 1 ] && [ -n "$1" ] || { echo "Usage: $0 <Owner>" >&2; exit 1; }
OWNER=$1
STACK=kv-network
TAG_RETRIES=3
TAG_RETRY_PAUSE=30
"$DIR/check-session.sh" >/dev/null

stamp() { echo "[$(date -u +%FT%TZ)] $*"; }
START=$SECONDS
phase_start() { PHASE_AT=$SECONDS; stamp "START $1"; }
phase_end() { stamp "END   $1 ($((SECONDS - PHASE_AT))s)"; }

phase_start delete
aws cloudformation delete-stack --stack-name "$STACK" --region "$AWS_REGION"
aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
phase_end delete

# The Tagging API lags behind deletion: one initial check plus up to TAG_RETRIES retries, each after TAG_RETRY_PAUSE seconds (max 4 checks, 90 s of waiting), then fail.
phase_start tagging-check
retry=0
while :; do
  LEFT=$(aws resourcegroupstaggingapi get-resources --region "$AWS_REGION" --tag-filters Key=Project,Values=capstone-kv --query 'ResourceTagMappingList' --output json)
  [ "$(echo "$LEFT" | tr -d '[:space:]')" = "[]" ] && break
  stamp "check $((retry + 1))/$((TAG_RETRIES + 1)): resources remain"
  echo "$LEFT"
  if [ "$retry" -ge "$TAG_RETRIES" ]; then
    echo "FAIL: tagged resources remain after delete" >&2
    exit 1
  fi
  retry=$((retry + 1))
  sleep "$TAG_RETRY_PAUSE"
done
stamp "tagging API empty"
phase_end tagging-check

phase_start create
"$DIR/deploy-network.sh" "$OWNER"
phase_end create

phase_start verify
"$DIR/verify-network.sh"
phase_end verify

stamp "TOTAL $((SECONDS - START))s"
