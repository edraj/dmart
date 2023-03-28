
podman build -t dmart -f Dockerfile ../../
podman run --name dmart -p 8282:8282 -d -it dmart


