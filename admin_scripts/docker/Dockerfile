FROM alpine:3.23

RUN set -eux \
  && apk add postgresql18 postgresql18-contrib postgresql18-openrc \
  && mkdir -p /run/postgresql && chown -R postgres:postgres /run/postgresql \
  && tr -dc A-Za-z0-9 </dev/urandom | head -c 13 > /tmp/pgpass \
  && su - postgres -c 'initdb --auth=md5 -U dmart --pwfile=/tmp/pgpass /var/lib/postgresql/18/data' \
  && su - postgres -c 'pg_ctl start -t 5000 -D /var/lib/postgresql/18/data' \
  && export PGPASSWORD=$(cat /tmp/pgpass) \
  && createdb -h 127.0.0.1 -U dmart dmart \
  && apk add git curl jq uv openrc python3 caddy bash file coreutils tzdata \
  && adduser -DH dmart \
  && git clone --depth 1 https://github.com/edraj/dmart.git /home/dmart \
  && cp /home/dmart/admin_scripts/docker/dmart.sysv /etc/init.d/dmart \
  && cp /home/dmart/admin_scripts/docker/config.ts /home/dmart/frontend/src/ \
  && apk add --virtual buildpkgs nodejs yarn \
  && cp /home/dmart/admin_scripts/docker/Caddyfile /etc/caddy/ \
  && uv venv /home/venv \
  && source /home/venv/bin/activate \
  && uv pip install -r /home/dmart/backend/requirements/core.txt \
  && uv cache clean \
  && cd /home/dmart/frontend/ \
  && sed -i 's/sysadmin//g' /home/dmart/frontend/src/App.svelte /home/dmart/frontend/vite.config.ts \
  && yarn \
  && yarn build \
  && rm -rf node_modules \
  && yarn cache clean --all \
  && apk del buildpkgs \
  && rm -rf /tmp/js-offline \
  && rm -rf /root/.cache /root/.local /var/cache/apk/ \
  # && apk add --no-cache su-exec tzdata openrc jq curl python3 py3-virtualenv caddy bash coreutils file \
  && mkdir -p /home/logs/dmart \
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
  && cp /home/dmart/backend/config.env.sample /home/dmart/backend/config.env \
  && echo "JWT_SECRET='$(tr -dc A-Za-z0-9 </dev/urandom | head -c 26)'" >> /home/dmart/backend/config.env \
  && echo "DATABASE_USERNAME='dmart'" >> /home/dmart/backend/config.env \
  && echo "DATABASE_PASSWORD='$(cat /tmp/pgpass)'" >> /home/dmart/backend/config.env \
  && echo "ACTIVE_DATA_DB='sql'" >> /home/dmart/backend/config.env \
  && echo "BASE_PATH='/dmart'" >> /home/dmart/backend/config.env \
  && rm -rf /tmp/* \
  && source /home/venv/bin/activate \
  && cd /home/dmart/backend \
  # && su - postgres -c 'pg_ctl restart -t 5000 -D /var/lib/postgresql/18/data' \
  && alembic upgrade head \
  && /home/venv/bin/python ./migrate.py json_to_db \
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
