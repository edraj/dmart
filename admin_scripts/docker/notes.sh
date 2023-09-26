
podman build -t dmart -f Dockerfile ../../
podman run --name dmart -p 8000:8000 -d -it dmart
podman exec -it -w /home/backend  dmart /home/venv/bin/python3.11 /home/backend/create_index.py --flushall
podman exec -it dmart /etc/init.d/dmart restart


# List all containers
podman ps -a --storage


# Sample container image
# echo -e 'FROM alpine:3.18\nRUN echo "hello world"' | podman build -t hello -


