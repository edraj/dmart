REDIS_HOST="$(./get_settings.py | jq -r .redis_host)"
RESULT+=$?
REDIS_PORT="$(./get_settings.py | jq -r .redis_port)"
RESULT+=$?
REDIS_PASSWORD="$(./get_settings.py | jq -r .redis_password)"
[ -z $REDIS_PASSWORD ] || REDIS_PASSWORD="--no-auth-warning -a $REDIS_PASSWORD" 

while true
    do
        redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ${REDIS_PASSWORD}  info | grep connected_clients
        redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ${REDIS_PASSWORD}  info | grep blocked_clients
        sleep 1
    done
