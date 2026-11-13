#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

ARN=$(aws sts get-caller-identity --region "$AWS_REGION" --query Arn --output text 2>/dev/null || true)
case "$ARN" in
  arn:aws:sts::*:assumed-role/*/*) ;;
  *) echo "Sandbox session missing or expired" >&2; exit 1 ;;
esac

ROLE=${ARN#*:assumed-role/}
echo "arn:aws:sts::<acct>:assumed-role/${ROLE%%/*}/<session>" >&2
echo "${ROLE%%/*}"
