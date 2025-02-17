#!/bin/bash

# Pull the latest changes from git
git pull

# Run Svelte check and build, then sync files
yarn cache clean
rm -rf node_modules yarn.lock /tmp/js-offline
yarn svelte-check && yarn build

# Check if Caddy or Nginx is active and perform rsync accordingly
if systemctl is-active --quiet caddy; then
  echo "Caddy is active. Syncing files to /var/www/html/sysadmin/"
  #mkdir -p /var/www/html/sysadmin/
  rm -rf /var/www/html/sysadmin/*
  rsync -av dist/client/ /var/www/html/sysadmin/
  #restorecon -v /var/www/html/*
  #ausearch -m avc -c caddy -ts recent  
  #systemctl restart caddy
elif systemctl is-active --quiet nginx; then
  echo "Nginx is active. Syncing files to /usr/share/nginx/html/"
  #mkdir -p /usr/share/nginx/html/sysadmin/
  rm -rf /usr/share/nginx/html/sysadmin/*
  rsync -av dist/client/ /usr/share/nginx/html/
  unlink /usr/share/nginx/html/index.html
  ln -s /usr/share/nginx/html/sysadmin/index.html /usr/share/nginx/html/index.html
  #restorecon -v /usr/share/nginx/html/*
  #ausearch -m avc -c nginx -ts recent
  #systemctl restart nginx 
else
  echo "No active web proxy service found."
fi

# Check if the dmart-frontend service is active under the current user and restart it if active
if systemctl --user is-active --quiet dmart-frontend; then
  echo "dmart-frontend service is active. Restarting the service..."
  systemctl --user restart dmart-frontend
else
  echo "dmart-frontend service is not active."
fi
