FROM python:3.14-alpine
# FROM alpine:latest

ADD https://raw.githubusercontent.com/edraj/dmart/refs/heads/master/admin_scripts/docker/dmart.sysv /root/dmart.sysv
ADD https://raw.githubusercontent.com/edraj/dmart/refs/heads/master/admin_scripts/docker/Caddyfile /root/Caddyfile
ADD https://raw.githubusercontent.com/edraj/dmart/refs/heads/master/admin_scripts/docker/config.json /root/config.json

RUN set -eux \
  && apk add postgresql18 postgresql18-contrib postgresql18-openrc \
  && mkdir -p /run/postgresql && chown -R postgres:postgres /run/postgresql \
  && tr -dc A-Za-z0-9 </dev/urandom | head -c 13 > /tmp/pgpass \
  && su - postgres -c 'initdb --auth=scram-sha-256 -U dmart --pwfile=/tmp/pgpass /var/lib/postgresql/18/data' \
  && su - postgres -c 'pg_ctl start -t 5000 -D /var/lib/postgresql/18/data' \
  && export PGPASSWORD=$(cat /tmp/pgpass) \
  && createdb -h 127.0.0.1 -U dmart dmart \
  && apk add curl jq uv openrc caddy bash file coreutils tzdata \
  && adduser -DH dmart \
  && cp /root/dmart.sysv /etc/init.d/dmart \
  && chmod a+x /etc/init.d/dmart \
  && cp /root/Caddyfile /etc/caddy/ \
  && uv venv /home/venv \
  && source /home/venv/bin/activate \
  && uv pip install dmart \
  && uv cache clean \
  && mkdir -p /home/logs/ \
  && touch /home/logs/caddy.log \
  && chmod -R g+xw /home/logs/ \
  && chown -R root:caddy /home/logs \
  && sed -i 's/^\(tty\d\:\:\)/#\1/g' /etc/inittab \
  && sed -i \
     -e 's/#rc_sys=".*"/rc_sys="docker"/g' \
     -e 's/#rc_env_allow=".*"/rc_env_allow="\*"/g' \
     -e 's/#rc_crashed_stop=.*/rc_crashed_stop=NO/g' \
     -e 's/#rc_crashed_start=.*/rc_crashed_start=YES/g' \
     -e 's/#rc_provide=".*"/rc_provide="loopback net"/g' \
     /etc/rc.conf \
  && rm -f /etc/init.d/hwdrivers \
     /etc/init.d/hwclock \
     /etc/init.d/hwdrivers \
     /etc/init.d/modules \
     /etc/init.d/modules-load \
     /etc/init.d/modloop \
     /etc/init.d/machine-id \
  && > /usr/libexec/rc/sh/rc-cgroup.sh \
  && sed -i 's/VSERVER/DOCKER/Ig' /usr/libexec/rc/sh/init.sh \
  && source /home/venv/bin/activate \
  && dmart init \
  # && cp /home/dmart/backend/config.env.sample /home/dmart/backend/config.env \
  # && echo "JWT_SECRET='$(tr -dc A-Za-z0-9 </dev/urandom | head -c 26)'" >> /home/dmart/backend/config.env \
  && echo "DATABASE_NAME='dmart'" >> /root/.dmart/config.env \
  && echo "DATABASE_DRIVER='postgresql+psycopg'" >> /root/.dmart/config.env \
  && echo "DATABASE_USERNAME='dmart'" >> /root/.dmart/config.env \
  && echo "DATABASE_PASSWORD='$(cat /tmp/pgpass)'" >> /root/.dmart/config.env \
  && echo "ACTIVE_DATA_DB='sql'" >> /root/.dmart/config.env \
  && echo "BASE_PATH='/dmart'" >> /root/.dmart/config.env \
  && cp /root/config.json /root/.dmart/ \
  && rm -rf /tmp/* \
  # && cd /home/dmart/backend \
  # && su - postgres -c 'pg_ctl restart -t 5000 -D /var/lib/postgresql/18/data' \
  && dmart migrate \
  && dmart json_to_db \
  # && echo 'data_dir="/var/lib/postgresql/18/data"' >> /etc/conf.d/postgresql \ 
  && rc-update add postgresql \
  && rc-update add dmart \
  && rc-update add caddy

LABEL org.label-schema.name="dmart" \
      org.label-schema.vendor="dmart.cc" \
      org.label-schema.description="Docker image for DMART with PostgreSQL (SQL MODE)" \
      org.label-schema.vcs-url="https://github.com/edraj/dmart" \
      org.label-schema.version="1.0" \
      org.label-schema.license="AGPLv3+"

# Optional external mount points
# VOLUME ["/home"]

# Start the init process
CMD ["/sbin/init"]
