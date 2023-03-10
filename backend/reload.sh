#!/bin/bash -x

source ./login_creds.sh

REDIS_HOST="$(./get_settings.py | jq -r .redis_host)"
REDIS_PORT="$(./get_settings.py | jq -r .redis_port)"
REDIS_PASSWORD="-a $(./get_settings.py | jq -r .redis_password)"
# APP_URL="$(./get_settings.py | jq -r .app_url)"
APP_URL="http://localhost:8282"

time ./create_index.py --flushall

which systemctl 2> /dev/null && systemctl --user list-units dmart.service > /dev/null && systemctl --user restart dmart.service
sleep 4

TOKEN=$(curl -s "${APP_URL}/user/login" -H 'Content-Type: application/json' -d "${SUPERMAN}" | jq -r '.records[0].attributes.access_token')
echo $TOKEN

curl -s -H "Authorization: Bearer ${TOKEN}" "${APP_URL}/user/profile" | jq '.records[0].attributes.roles'

redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} --no-auth-warning ${REDIS_PASSWORD} JSON.GET users_permissions_dmart | jq -R '.|fromjson|keys|length'
