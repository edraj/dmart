#!/bin/bash
pip3.11 install --user -r backend/requirements.txt
pip3.11 install --user check-jsonschema

mkdir ~/logs/dmart ~/spaces -p
redis-cli -h 127.0.0.1 -p 6389 --no-auth-warning -a xxxx flushall


cp -a admin/dmart.service* ~/.config/systemd/user/


systemctl --user daemon-reload
loginctl enable-linger
systemctl --user enable dmart
systemctl --user start dmart
systemctl --user status dmart
systemctl --user edit dmart
systemctl --user show dmart | grep Environment
systemctl --user show-environment



# Helper commands

# check the validity of json files against schema
# for my in $(ls -1 *.json); do echo -n "$my "; check-jsonschema --schemafile ../../schema/governorate.json $my; done;


# View json content of redis json object
# redis-cli --no-auth-warning -a xxxx JSON.GET users_permissions:dmart | jq -R '.|fromjson'


# View the service logs
journalctl --user-unit dmart.service --follow -o json | jq '.MESSAGE | fromjson'

# Build python 3.11 from source
# As root user
sudo dnf install gcc openssl-devel bzip2-devel libffi-devel sqlite-devel
sudo dnf groupinstall "Development Tools"
wget 'https://www.python.org/ftp/python/3.11.2/Python-3.11.2.tgz'
tar xzf Python-3.11.2.tgz
cd Python-3.11.2/
./configure --enable-optimizations
sudo make altinstall

# As regular user
ln -s /usr/local/bin/python3.11 ~/.local/bin/python3
ln -s /usr/local/bin/python3.11 ~/.local/bin/python
ln -s /usr/local/bin/pip3.11 ~/.local/bin/pip
