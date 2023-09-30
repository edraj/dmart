#!/bin/bash -x 

# Steps to get a fully working instance of dmart backend + admin ui + redis

# 0. Delete existing dmart container
podman rm -f dmart
podman rmi dmart

# 1. Create the container image
podman build -t dmart -f Dockerfile

# 2. Instaniate the the container
podman run --name dmart -p 8000:8000 -d -it dmart

# 3. Set admin and testuser password
podman exec -it -w /home/backend dmart /home/venv/bin/python3.11 ./set_admin_passwd.py

# 4. Load the initial / sample space data and restart the service
podman exec -it -w /home/backend dmart bash -c 'source /home/venv/bin/activate && ./reload.sh'

# 5. Run automated tests -- using pytest
podman exec -it -w /home/backend dmart /home/venv/bin/python3.11 -m pytest

# 6. Run automated tests -- using curl.sh
podman exec -it -w /home/backend dmart ./curl.sh

# 7. Print the server manifest
podman exec -it -w /home/backend dmart ./manifest.sh

# 8. Now open the browser to http://localhost:8000
xdg-open http://localhost:8000

# 9. Run source code linters
podman exec -it -w /home/backend dmart bash -c 'source /home/venv/bin/activate && ./pylint.sh'

# 10. Run health-check
podman exec -it -w /home/backend  dmart /home/venv/bin/python3.11 ./health_check.py

# Reindex the data
# podman exec -it -w /home/backend dmart /home/venv/bin/python3.11 ./create_index.py --flushall
# podman exec -it dmart /etc/init.d/dmart restart

# List all containers
# podman ps -a --storage

# Sample container image
# echo -e 'FROM alpine:3.18\nRUN echo "hello world"' | podman build -t hello -
#
