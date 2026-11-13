#!/usr/bin/env bash
# Usage: labrole-dissect.sh [role-name]  (default: role of the current session)
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"

ROLE=${1:-$("$DIR/check-session.sh")}
OUT="$DIR/../docs/evidence/labrole"
mkdir -p "$OUT"

# Session name and UserId carry the student's e-mail: redact before writing.
redact() {
  sed 's#assumed-role/\([^/]*\)/[^"[:space:]]*#assumed-role/\1/<session>#; s#\(AROA[A-Z0-9]*\):[^"[:space:]]*#\1:<session>#'
}

# run <name> <aws args...>: evidence to <role>-<name>.txt, never aborts.
run() {
  local name=$1; shift
  { echo "\$ aws $*"; aws "$@" --region "$AWS_REGION" 2>&1 || echo "[exit $?]"; } | redact > "$OUT/${ROLE}-${name}.txt"
  echo "$name: $(sed -n 's/.*An error occurred (\([A-Za-z]*\)).*/denied (\1)/p' "$OUT/${ROLE}-${name}.txt" | head -n 1)"
}

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE}"

run sts-get-caller-identity sts get-caller-identity
run iam-get-role iam get-role --role-name "$ROLE"
run iam-get-role-LabRole iam get-role --role-name LabRole
run iam-list-attached-role-policies iam list-attached-role-policies --role-name "$ROLE"
run iam-list-role-policies iam list-role-policies --role-name "$ROLE"

for arn in $(aws iam list-attached-role-policies --role-name "$ROLE" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || true); do
  n=${arn##*/}
  run "iam-get-policy-$n" iam get-policy --policy-arn "$arn"
  v=$(aws iam get-policy --policy-arn "$arn" --query Policy.DefaultVersionId --output text 2>/dev/null || true)
  [ -n "$v" ] && run "iam-get-policy-version-$n" iam get-policy-version --policy-arn "$arn" --version-id "$v"
done
for p in $(aws iam list-role-policies --role-name "$ROLE" --query 'PolicyNames[]' --output text 2>/dev/null || true); do
  run "iam-get-role-policy-$p" iam get-role-policy --role-name "$ROLE" --policy-name "$p"
done

TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:ListAllMyBuckets","Resource":"*"}]}'
run iam-create-user iam create-user --user-name kv-probe-user
run iam-create-group iam create-group --group-name kv-probe-group
run iam-create-policy iam create-policy --policy-name kv-probe-policy --policy-document "$POLICY"
run iam-create-role iam create-role --role-name kv-probe-role --assume-role-policy-document "$TRUST"

# A probe that succeeded must not stay behind.
grep -q '"UserName"' "$OUT/${ROLE}-iam-create-user.txt" && run iam-delete-user iam delete-user --user-name kv-probe-user
grep -q '"GroupName"' "$OUT/${ROLE}-iam-create-group.txt" && run iam-delete-group iam delete-group --group-name kv-probe-group
grep -q '"Arn"' "$OUT/${ROLE}-iam-create-policy.txt" && run iam-delete-policy iam delete-policy --policy-arn "arn:aws:iam::${ACCOUNT}:policy/kv-probe-policy"
grep -q '"RoleName"' "$OUT/${ROLE}-iam-create-role.txt" && run iam-delete-role iam delete-role --role-name kv-probe-role

run iam-simulate-principal-policy iam simulate-principal-policy --policy-source-arn "$ROLE_ARN" \
  --action-names ec2:RunInstances ec2:CreateVpc iam:CreateRole s3:CreateBucket cloudformation:CreateStack \
  --query 'EvaluationResults[].[EvalActionName,EvalDecision]' --output text
if grep -rq '@' "$OUT"; then echo "e-mail leaked into evidence" >&2; exit 1; fi
exit 0
