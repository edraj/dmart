#!/bin/bash

git pull
yarn svelte-check && yarn build && rsync -av dist/client/ /var/www/html/sysadmin/
systemctl --user restart dmart-frontend
