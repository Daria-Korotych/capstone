#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$DIR/env.sh"
"$DIR/check-session.sh" >/dev/null

STACK=kv-network
VPC_CIDR=10.20.0.0/16
PUBLIC_CIDRS="10.20.0.0/24 10.20.1.0/24"
PRIVATE_CIDRS="10.20.10.0/24 10.20.11.0/24"
EXPORTS="VpcId PublicSubnet1Id PublicSubnet2Id PrivateSubnet1Id PrivateSubnet2Id"
FAILED=0

# Every query tolerates failure: a missing stack must yield FAIL lines, not abort the script.
a() { aws "$@" --region "$AWS_REGION" 2>/dev/null || true; }
report() { # name, ok(0/1)
  if [ "$2" = 0 ]; then echo "PASS $1"; else echo "FAIL $1"; FAILED=1; fi
}
check() { # name, command...
  local name=$1; shift
  if "$@" >/dev/null 2>&1; then report "$name" 0; else report "$name" 1; fi
}

STATUS=$(a cloudformation describe-stacks --stack-name $STACK --query 'Stacks[0].StackStatus' --output text)
check "stack exists" test "$STATUS" = CREATE_COMPLETE -o "$STATUS" = UPDATE_COMPLETE

VPC=$(a ec2 describe-vpcs --filters Name=tag:Project,Values=capstone-kv --query 'Vpcs[0].VpcId' --output text)
[ "$VPC" = None ] && VPC=""
VPC_CIDR_ACTUAL=""
[ -n "$VPC" ] && VPC_CIDR_ACTUAL=$(a ec2 describe-vpcs --vpc-ids "$VPC" --query 'Vpcs[0].CidrBlock' --output text)
check "vpc cidr" test "$VPC_CIDR_ACTUAL" = "$VPC_CIDR"

SUBNETS='{"Subnets":[]}'
[ -n "$VPC" ] && SUBNETS=$(a ec2 describe-subnets --filters Name=vpc-id,Values="$VPC" --output json)
[ -z "$SUBNETS" ] && SUBNETS='{"Subnets":[]}'
sub() { echo "$SUBNETS" | jq -r "$1"; }

WANT=$(echo $PUBLIC_CIDRS $PRIVATE_CIDRS | tr ' ' '\n' | sort | tr '\n' ' ')
GOT=$(sub '[.Subnets[].CidrBlock]|sort|.[]' | tr '\n' ' ')
check "four subnet cidrs" test "$WANT" = "$GOT"

az_distinct() { # cidrs -> two distinct AZs
  local n
  n=$(for c in $1; do sub ".Subnets[]|select(.CidrBlock==\"$c\")|.AvailabilityZone"; done | sort -u | wc -l)
  [ "$n" -eq 2 ]
}
check "azs distinct" bash -c "$(declare -f sub az_distinct); SUBNETS='$SUBNETS'; az_distinct '$PUBLIC_CIDRS' && az_distinct '$PRIVATE_CIDRS'"

map_is() { # cidrs, expected
  local c
  for c in $1; do
    [ "$(sub ".Subnets[]|select(.CidrBlock==\"$c\")|.MapPublicIpOnLaunch")" = "$2" ] || return 1
  done
}
check "map public ip" bash -c "$(declare -f sub map_is); SUBNETS='$SUBNETS'; map_is '$PUBLIC_CIDRS' true && map_is '$PRIVATE_CIDRS' false"

routes_of() { # cidr -> GatewayId list of routes in the subnet's route table
  local id
  id=$(sub ".Subnets[]|select(.CidrBlock==\"$1\")|.SubnetId")
  [ -n "$id" ] || return 1
  a ec2 describe-route-tables --filters Name=association.subnet-id,Values="$id" --output json
}
PUB_OK=0; PRIV_OK=0
for c in $PUBLIC_CIDRS; do
  rt=$(routes_of "$c" || true)
  [ -n "$rt" ] && echo "$rt" | jq -e '.RouteTables|length==1 and (.[0].Routes|any(.DestinationCidrBlock=="0.0.0.0/0" and ((.GatewayId//"")|startswith("igw-"))))' >/dev/null || PUB_OK=1
done
[ -z "$SUBNETS" ] || [ "$(sub '.Subnets|length')" = 0 ] && PUB_OK=1
report "public default route to igw" $PUB_OK
for c in $PRIVATE_CIDRS; do
  rt=$(routes_of "$c" || true)
  [ -n "$rt" ] && echo "$rt" | jq -e '.RouteTables|length==1 and (.[0].Routes|all(.GatewayId=="local"))' >/dev/null || PRIV_OK=1
done
[ "$(sub '.Subnets|length')" = 0 ] && PRIV_OK=1
report "private local routes only" $PRIV_OK

# Resources from check 8 (the untagged main route table is AWS-created, so only associated custom ones count).
RES='[]'
if [ -n "$VPC" ]; then
  RT=$(a ec2 describe-route-tables --filters Name=vpc-id,Values="$VPC" --output json)
  IGW=$(a ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values="$VPC" --output json)
  VPCJ=$(a ec2 describe-vpcs --vpc-ids "$VPC" --output json)
  RES=$(jq -n --argjson s "${SUBNETS:-null}" --argjson r "${RT:-null}" --argjson i "${IGW:-null}" --argjson v "${VPCJ:-null}" \
    '[($v.Vpcs[]?),($s.Subnets[]?),($i.InternetGateways[]?),($r.RouteTables[]?|select(any(.Associations[]?; .Main|not)))]
     | map({Tags:(.Tags//[])})') || RES='[]'
fi
check "required tags" bash -c "echo '$RES' | jq -e 'length>=8 and all(.[]; (.Tags|map(.Key)) as \$k | (\"Project\",\"Environment\",\"Milestone\",\"Owner\") as \$t | \$k|index(\$t) != null)'"

EXP=$(a cloudformation list-exports --query 'Exports[].Name' --output text)
MISSING=0
for e in $EXPORTS; do echo "$EXP" | tr '\t' '\n' | grep -qx "$STACK-$e" || MISSING=1; done
report "exports present" $MISSING

NAT_COUNT=x
[ -n "$VPC" ] && NAT_COUNT=$(a ec2 describe-nat-gateways --filter Name=vpc-id,Values="$VPC" Name=state,Values=pending,available,deleting --query 'length(NatGateways)' --output text)
check "no nat gateway" test "$NAT_COUNT" = 0

APP=$(a cloudformation describe-stacks --stack-name $STACK --query "Stacks[0].Parameters[?ParameterKey=='ApplicationName'].ParameterValue" --output text)
ENV=$(a cloudformation describe-stacks --stack-name $STACK --query "Stacks[0].Parameters[?ParameterKey=='Environment'].ParameterValue" --output text)
check "name tags prefix" bash -c "[ -n '$APP' ] && [ -n '$ENV' ] && echo '$RES' | jq -e --arg p '$APP-$ENV-' 'length>=8 and all(.[]; (.Tags|map(select(.Key==\"Name\").Value)|first // \"\")|startswith(\$p))'"

exit $FAILED
