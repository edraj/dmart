#!/bin/bash

which vegeta > /dev/null || ( echo "Can'd find vegeta, download and put on path : https://github.com/tsenart/vegeta"; exit )

API_URL="http://127.0.0.1:8282"
CT="Content-Type: application/json"

source ../login_creds.sh
declare -i RESULT=0


AUTH_TOKEN=$(curl -i -s -H "$CT" -d "$SUPERMAN" ${API_URL}/user/login  | grep set-cookie | sed 's/^[^=]*=\(.*\); Http.*$/\1/g')
RESULT+=$?
echo "Logged-in as super admin" >&2

cat <<EOF | vegeta attack -duration=10s | tee results.bin | vegeta report  # -type="json" | jq .

# Plain service api main point 
GET ${API_URL}

# Who am i
GET ${API_URL}/info/me
Authorization: Bearer ${AUTH_TOKEN}

# Get profile
GET ${API_URL}/user/profile
Authorization: Bearer ${AUTH_TOKEN}

# Update admin Email
POST ${API_URL}/managed/request
Content-Type: application/json
Authorization: Bearer ${AUTH_TOKEN}
@./update_user_email.json

# Reload security
GET ${API_URL}/managed/reload-security-data
Authorization: Bearer ${AUTH_TOKEN}

# Query spaces
POST ${API_URL}/managed/query
Content-Type: application/json
Authorization: Bearer ${AUTH_TOKEN}
@./query_spaces.json

# Server manifest
GET ${API_URL}/info/manifest
Authorization: Bearer ${AUTH_TOKEN}

# Export CSV
POST ${API_URL}/managed/csv
Content-Type: application/json
Authorization: Bearer ${AUTH_TOKEN}
@./export_csv.json

EOF

RESULT+=$?
echo "Sum of exit codes = ${RESULT}"

exit

