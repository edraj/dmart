apk add gcc abuild coreutils linux-headers make musl-dev openssl-dev g++ bash make cmake atools

# apk add gcc abuild  --no-cache
# apk add --no-cache --virtual .build-deps coreutils gcc linux-headers make musl-dev openssl-dev g++ bash make cmake
# apk add abuild atools --no-cache

build-keygen -a -i

# git clone -b 'v1.8.1' --single-branch --depth 1 --recursive https://github.com/RediSearch/RediSearch.git
# cd RedisSearch
# make build
# cp ./src/redisearch.so /usr/lib/
# sed -ri 's!^# loadmodule /path/to/my_module.so$!loadmodule /usr/lib/redisearch.so!' /etc/redis.conf

# apk del --no-network .build-deps
# abuild-keygen -a -i
# abuild-sign -k /path/to/alpine@example.com-59ea3c02.rsa /apk/v3.6/main/x86_64/APKINDEX.tar.gz

# mkdir /root/repo/v3.12/main/x86_64 -p


# Building apk


cd redisearch
apkbuild-lint APKBUILD
abuild -rF -P /usr/share/imxrepo
abuild-sign -k ~/.abuild/root@i0.imx.sh-5f197da7.rsa /usr/share/imxrepo/packages/x86_64/APKINDEX.tar.gz


abuild -r -P /home/alpine/apkrepo/
