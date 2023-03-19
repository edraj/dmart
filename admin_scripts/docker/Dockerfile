FROM alpine:3.17

# Optional external mount points
VOLUME ["/home"]

LABEL org.label-schema.name="dmart" \
      org.label-schema.vendor="dmart.cc" \
      org.label-schema.description="Docker image for DMART with Redis 7.x with RedisJson (ReJson) and RediSearch" \
      org.label-schema.vcs-url="https://github.com/edraj/dmart" \
      org.label-schema.version="1.0" \
      org.label-schema.license="AGPLv3+"

COPY admin_scripts/docker/alpine@imx.sh-5f19b383.rsa.pub /etc/apk/keys/
COPY backend /home/backend/
COPY cli /home/cli/
COPY frontend /home/frontend/

RUN set -eux \
  mkdir -p /home/redis /home/spaces /home/logs/dmart /home/logs/redis \
  && echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories \
  && apk add --no-cache jq curl python3 py3-pip \ 
  && python -m ensurepip --upgrade \
  && pip install --upgrade pip \
  && pip install -r /home/backend/requirements.txt \
  && pip cache purge \
  && apk add --no-cache redis redisearch redisjson --repository=https://apk.imx.sh/packages  \
  && apk add --no-cache git su-exec tzdata openrc \
  && apk add --no-cache nodejs yarn \
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
  && rc-update add redis 


# EXPOSE 6379/tcp

# CMD ["/redis.sh"]

CMD ["/sbin/init"]
