#!/bin/bash
yarn install && yarn build && rsync -av dist/ /var/www/html/sysadmin
