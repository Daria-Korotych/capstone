#!/usr/bin/env bash
# Usage: smoke.sh <coordinator-url>. End-to-end check of a running cluster.
set -euo pipefail

for tool in curl jq; do
  command -v "$tool" >/dev/null || { echo "SMOKE FAILED: $tool is required but not installed" >&2; exit 1; }
done

base="${1:?usage: smoke.sh <coordinator-url>}"
expected_shards=2
wait_timeout_s=40
poll_interval_s=2
table="smoke_$(date +%s)_$$"
item_url="$base/tables/$table/items/k1"
body='{"v":"hello"}'
expected='{"v":"hello","id":"k1"}'

fail() { echo "SMOKE FAILED: $*" >&2; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

deadline=$((SECONDS + wait_timeout_s))
until [ "$(curl -sf "$base/shards" | jq length 2>/dev/null || true)" = "$expected_shards" ]; do
  [ "$SECONDS" -lt "$deadline" ] || fail "fewer than $expected_shards shards registered after ${wait_timeout_s}s"
  sleep "$poll_interval_s"
done

table_def=$(jq -cn --arg name "$table" '{name: $name, partition_key: "id"}')
[ "$(status -X POST "$base/tables" -H 'content-type: application/json' -d "$table_def")" = 201 ] || fail "create table"
[ "$(status -X PUT "$item_url" -H 'content-type: application/json' -d "$body")" = 201 ] || fail "put"
[ "$(status -I "$item_url")" = 200 ] || fail "head after put"
[ "$(curl -sf "$item_url" | jq -cS .)" = "$(jq -cS . <<<"$expected")" ] || fail "get does not match"
[ "$(status -X DELETE "$item_url")" = 204 ] || fail "delete"
[ "$(status "$item_url")" = 404 ] || fail "get after delete is not 404"
echo "SMOKE OK"
