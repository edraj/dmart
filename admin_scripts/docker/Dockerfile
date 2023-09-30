FROM alpine:3.18

# Optional external mount points
# VOLUME ["/home"]

LABEL org.label-schema.name="dmart" \
      org.label-schema.vendor="dmart.cc" \
      org.label-schema.description="Docker image for DMART with Redis 7.x with RedisJson (ReJson) and RediSearch" \
      org.label-schema.vcs-url="https://github.com/edraj/dmart" \
      org.label-schema.version="1.0" \
      org.label-schema.license="AGPLv3+"

# COPY admin_scripts/docker/alpine@imx.sh-5f19b383.rsa.pub /etc/apk/keys/
# COPY ./ /home/

# RUN set -eux 
RUN set -eux \
  && apk add --no-cache git \
  && git clone https://github.com/edraj/dmart.git /home/ \
  && mkdir -p /home/redis /home/logs/dmart /home/logs/redis \
  && cp /home/admin_scripts/docker/alpine@imx.sh-5f19b383.rsa.pub /etc/apk/keys/ \
  && cp /home/admin_scripts/docker/dmart.sysv /etc/init.d/dmart && chmod a+x /etc/init.d/dmart \
  && cp /home/admin_scripts/docker/gitconfig /etc/gitconfig \
  && cp /home/admin_scripts/docker/config.ts /home/frontend/src/ \
  && cp /home/admin_scripts/docker/config.env /home/backend/ \
  && chmod a+x /home/backend/*.py \
  && echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories \
  && apk add --no-cache jq curl python3 py3-pip py3-wheel py3-setuptools py3-virtualenv gcc musl-dev python3-dev caddy bash coreutils file \
  && cp /home/admin_scripts/docker/Caddyfile /etc/caddy/ \
  && apk add --no-cache redis redisearch redisjson --repository=https://apk.imx.sh/packages  \
  && apk add --no-cache git su-exec tzdata openrc \
  && virtualenv --python=/usr/bin/python3.11 /home/venv \
  && source /home/venv/bin/activate \
  && pip install --upgrade pip \
  && pip install -r /home/backend/requirements.txt -r /home/backend/test-requirements.txt -r /home/backend/plugins-requirements.txt \
  && pip cache purge \
  && apk add --no-cache nodejs yarn \
  && cd /home/frontend/ && yarn install && yarn build && rm -rf node_modules && yarn cache clean \
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
  && sed -i 's/cgroup_add_service /# cgroup_add_service /g' /lib/rc/sh/openrc-run.sh \
  && sed -i 's/VSERVER/DOCKER/Ig' /lib/rc/sh/init.sh \
  && rc-update add redis \
  && rc-update add dmart \
  && rc-update add caddy

  # && /etc/init.d/redis start \
  # && cd /home/backend && ./create_index.py --flushall \
  #  && /etc/init.d/redis stop \

# EXPOSE 6379/tcp
# CMD ["/redis.sh"]
CMD ["/sbin/init"]
