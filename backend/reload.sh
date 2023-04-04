#!/bin/bash

declare -i RESULT=0
source ./login_creds.sh
RESULT+=$?

REDIS_HOST="$(./get_settings.py | jq -r .redis_host)"
RESULT+=$?
REDIS_PORT="$(./get_settings.py | jq -r .redis_port)"
RESULT+=$?
REDIS_PASSWORD="-a $(./get_settings.py | jq -r .redis_password)"
RESULT+=$?
PORT="$(./get_settings.py | jq -r .listening_port)"
RESULT+=$?
# APP_URL="$(./get_settings.py | jq -r .app_url)"
APP_URL="http://localhost:$PORT"

time ./create_index.py --flushall
RESULT+=$?

which systemctl 2> /dev/null && systemctl --user list-units dmart.service > /dev/null && systemctl --user restart dmart.service
RESULT+=$?
sleep 4

TOKEN=$(curl -s "${APP_URL}/user/login" -H 'Content-Type: application/json' -d "${SUPERMAN}" | jq -r '.records[0].attributes.access_token')
RESULT+=$?
echo $TOKEN

curl -s -H "Authorization: Bearer ${TOKEN}" "${APP_URL}/user/profile" | jq '.records[0].attributes.roles'
RESULT+=$?

redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} --no-auth-warning ${REDIS_PASSWORD} JSON.GET users_permissions_dmart | jq -R '.|fromjson|keys|length'
RESULT+=$?


echo "Sum of exist codes = $RESULT" 
exit $RESULT
