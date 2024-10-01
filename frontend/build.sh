#!/bin/bash

# Pull the latest changes from git
git pull

# Run Svelte check and build, then sync files
yarn svelte-check && yarn build

# Check if Caddy or Nginx is active and perform rsync accordingly
if systemctl is-active --quiet caddy; then
  echo "Caddy is active. Syncing files to /var/www/html/sysadmin/"
  rsync -av dist/client/ /var/www/html/sysadmin/
elif systemctl is-active --quiet nginx; then
  echo "Nginx is active. Syncing files to /usr/share/nginx/html/"
  rsync -av dist/client/ /usr/share/nginx/html/
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
