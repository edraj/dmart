# Stage 1: Build stage
FROM alpine:3.18 AS builder

# Install necessary packages for building
RUN set -eux \
  && apk add git curl openssh-client \
  && git clone --depth 1 https://github.com/edraj/dmart.git /home/ \
  && mkdir -p /home/redis /home/logs/dmart /home/logs/redis \
  && cp /home/admin_scripts/docker/alpine@imx.sh-5f19b383.rsa.pub /etc/apk/keys/ \
  && cp /home/admin_scripts/docker/dmart.sysv /etc/init.d/dmart \
  && cp /home/admin_scripts/docker/gitconfig /etc/gitconfig \
  && cp /home/admin_scripts/docker/config.ts /home/frontend/src/ \
  && cp /home/admin_scripts/docker/config.env /home/backend/ \
  && echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories \
  && apk add git su-exec tzdata openrc jq curl python3 py3-virtualenv caddy bash coreutils file \
  && apk add --virtual buildpkgs nodejs npm gcc libffi-dev make g++ musl-dev py3-pip python3-dev py3-wheel py3-setuptools \
  && apk add redis redisearch redisjson --repository=https://apk.imx.sh/packages \
  && cp /home/admin_scripts/docker/Caddyfile /etc/caddy/ \
  && virtualenv --python=/usr/bin/python3.11 /home/venv \
  && source /home/venv/bin/activate \
  && pip install -r /home/backend/requirements.txt \
  && pip cache purge \
  && cd /home/frontend/ && npm install && npm run build && rm -rf node_modules && npm cache clean --force \
  && apk del buildpkgs \
  && rm -rf /tmp/js-offline \
  && rm -rf /root/.cache /root/.local /var/cache/apk/

# Stage 2: Final stage
FROM alpine:3.18

# Copy necessary files from build stage
COPY --from=builder /home /home
COPY --from=builder /etc/apk/keys/alpine@imx.sh-5f19b383.rsa.pub /etc/apk/keys/
COPY --from=builder /etc/init.d/dmart /etc/init.d/dmart
COPY --from=builder /etc/gitconfig /etc/gitconfig
COPY --from=builder /home/venv /home/venv
COPY --from=builder /etc/caddy/Caddyfile /etc/caddy/

# Install runtime dependencies
RUN set -eux \
  && apk add --no-cache su-exec tzdata openrc jq curl python3 py3-virtualenv caddy bash coreutils file \
  && apk add redis redisearch redisjson --repository=https://apk.imx.sh/packages \
  && mkdir -p /home/redis /home/logs/dmart /home/logs/redis \
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

LABEL org.label-schema.name="dmart" \
      org.label-schema.vendor="dmart.cc" \
      org.label-schema.description="Docker image for DMART with Redis 7.x with RedisJson (ReJson) and RediSearch" \
      org.label-schema.vcs-url="https://github.com/edraj/dmart" \
      org.label-schema.version="1.0" \
      org.label-schema.license="AGPLv3+"

# Optional external mount points
# VOLUME ["/home"]

# Expose Redis port
# EXPOSE 6379/tcp
# CMD ["/redis.sh"]

# Start the init process
CMD ["/sbin/init"]