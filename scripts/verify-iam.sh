#!/usr/bin/env bash
set -euo pipefail
# Allowlist: every Action of every Allow statement must be a List/Describe/Get action and never s3:GetObject*.
# NotAction, Deny and bare wildcards fail. Returns non-zero (never aborts) on any bad input.
static_readonly() { # policy file
  jq -e '
    (.Statement | if type == "array" then . else [.] end) as $st
    | ($st | length > 0)
      and ($st | all(.[];
        .Effect == "Allow" and (has("NotAction") | not) and has("Action")
        and (.Action | if type == "array" then . else [.] end
             | length > 0 and all(.[]; type == "string"
                 and test("^[a-z0-9-]+:(List|Describe|Get)[A-Za-z]*\\*?$")
                 and (test("^s3:(GetO|Get\\*$)") | not)))))' "$1" >/dev/null 2>&1
}

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"
"$DIR/check-session.sh" >/dev/null

ROOT=$(dirname "$DIR")
TEMPLATE=$ROOT/infra/iam.yaml
EVIDENCE=$ROOT/docs/evidence/iam
WRITE_ACTIONS="ec2:CreateVpc s3:PutObject iam:CreateRole cloudformation:DeleteStack"
VIEW_ACTIONS="ec2:DescribeVpcs cloudformation:DescribeStacks"
FAILED=0

report() { # name, ok(0/1)
  if [ "$2" = 0 ]; then echo "PASS $1"; else echo "FAIL $1"; FAILED=1; fi
}
check() { # name, command...
  local name=$1; shift
  if "$@" >/dev/null 2>&1; then report "$name" 0; else report "$name" 1; fi
}

check "template exists" test -f "$TEMPLATE"
if [ ! -f "$TEMPLATE" ]; then
  echo "FAIL nothing further can be checked without $TEMPLATE"
  exit 1
fi

check "cfn-lint" "$ROOT/.venv/bin/cfn-lint" "$TEMPLATE"
check "validate-template" aws cloudformation validate-template --template-body "file://$TEMPLATE" --region "$AWS_REGION"

# cfn-flip leaves Fn::Sub unresolved; substitute region and account so the simulator sees real ARNs.
ACCOUNT=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
POLICY=$WORK/policy.json
if ! "$ROOT/.venv/bin/cfn-flip" -j "$TEMPLATE" | jq --arg region "$AWS_REGION" --arg account "$ACCOUNT" '
  .Resources.ReadOnlyPolicy.Properties.PolicyDocument
  | walk(if type == "object" and has("Fn::Sub")
         then .["Fn::Sub"] | gsub("\\$\\{AWS::Region\\}"; $region) | gsub("\\$\\{AWS::AccountId\\}"; $account)
         else . end)' >"$POLICY" 2>/dev/null; then
  echo "FAIL policy document extraction (cfn-flip/jq)"
  exit 1
fi
check "policy document extracted" jq -e '.Statement|length>0' "$POLICY"

STACK_ARN_PREFIX=arn:aws:cloudformation:$AWS_REGION:$ACCOUNT:stack
SIM_ERR=$WORK/sim-error.txt
SIMULATOR_DENIED=0

sim() { # name, expected decision, actions, resource arn
  local name=$1 want=$2 actions=$3 resource=$4 out bad
  # shellcheck disable=SC2086
  if ! out=$(aws iam simulate-custom-policy --region "$AWS_REGION" \
      --policy-input-list "$(jq -c . "$POLICY")" \
      --action-names $actions --resource-arns "$resource" \
      --query 'EvaluationResults[].[EvalActionName,EvalDecision]' --output json 2>"$SIM_ERR"); then
    if grep -qE 'AccessDenied|not authorized' "$SIM_ERR"; then SIMULATOR_DENIED=1; return 0; fi
    report "$name" 1; return 0
  fi
  bad=$(echo "$out" | jq --arg want "$want" '[.[]|select(.[1]!=$want)]|length')
  echo "     $name: $(echo "$out" | jq -c .)"
  if [ "$bad" = 0 ] && [ "$(echo "$out" | jq length)" = "$(echo "$actions" | wc -w | tr -d ' ')" ]; then
    report "$name" 0
  else
    report "$name" 1
  fi
}

sim "write actions implicitDeny" implicitDeny "$WRITE_ACTIONS" '*'
if [ "$SIMULATOR_DENIED" = 0 ]; then
  sim "view actions allowed (ec2)" allowed "ec2:DescribeVpcs" '*'
  sim "view actions allowed (project stack)" allowed "cloudformation:DescribeStacks" "$STACK_ARN_PREFIX/kv-network/*"
  sim "object content not readable" implicitDeny "s3:GetObject" 'arn:aws:s3:::capstone-kv-data/x'
  sim "bucket metadata allowed (project bucket)" allowed "s3:GetBucketLocation" 'arn:aws:s3:::capstone-kv-data'
  sim "bucket metadata denied (other bucket)" implicitDeny "s3:GetBucketLocation" 'arn:aws:s3:::other-bucket'
  sim "stack description denied (other stack)" implicitDeny "cloudformation:DescribeStacks" "$STACK_ARN_PREFIX/other/*"
fi

if [ "$SIMULATOR_DENIED" = 1 ]; then
  echo "SKIP simulator denied by sandbox role"
  mkdir -p "$EVIDENCE"
  # The error text carries the session name, which is an e-mail address: redact it.
  sed -E 's#(assumed-role/[^/]+/)[^ ]+#\1<session>#g' "$SIM_ERR" >"$EVIDENCE/simulator-denied.txt"
fi

check "static: read-only allowlist" static_readonly "$POLICY"

# The wildcard-resource statement may hold only List/Describe actions.
check "wildcard statement is List/Describe only" jq -e '
  [.Statement[]|select(.Resource|(if type=="array" then . else [.] end)|index("*"))|.Action|if type=="array" then .[] else . end]
  | length>0 and all(.[]; split(":")[1]|test("^(List|Describe)"))' "$POLICY"

exit $FAILED
