#!/bin/bash

mkdir ~/redis
cp myredis.conf ~/redis/

# Add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1'
sudo cp 10-redis.conf /etc/sysctl.d/
sudo sysctl vm.overcommit_memory=1

# Grant read access to redis modules
sudo chmod -R o+rx /usr/lib64/redis/

cp redis.service  ~/.config/systemd/user/
systemctl --user --daemon-reload

systemctl --user start redis


