#!/bin/bash 

source ./login_creds.sh

APP_URL="http://localhost:8282"


TOKEN=$(curl -s "${APP_URL}/user/login" -H 'Content-Type: application/json' -d "${SUPERMAN}" | jq -r '.records[0].attributes.access_token')
# curl -s -H "Authorization: Bearer ${TOKEN}" "${APP_URL}/managed/reload-security-data" | jq . 
# curl -s -H "Authorization: Bearer ${TOKEN}" "${APP_URL}/info/me" | jq . 
curl -s -H "Authorization: Bearer ${TOKEN}" "${APP_URL}/info/manifest" | jq . 
# curl -s -H "Authorization: Bearer ${TOKEN}" "${APP_URL}/info/settings" | jq . 
