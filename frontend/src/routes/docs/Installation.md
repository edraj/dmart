<script>
  import CLITest from "./assets/curl-test.png";
  import PYTest from "./assets/pytest.png";
  import AdminUI1 from "./assets/admin_ui_1.png";
  import AdminUI2 from "./assets/admin_ui_2.png";
  import CLI from "./assets/cli.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

## Installation

### Container (recommended)

Using podman (or docker), dmart can be fully setup and configured in few minutes.

You only need a command line console, git and podman (or docker). 

#### Steps
```
# Clone the git repo
git clone https://github.com/edraj/dmart.git
cd dmart/admin_scripts/docker

# Build the container
podman build -t dmart -f Dockerfile

# Run the container
podman run --name dmart -p 8000:8000 -d -it dmart

# Set the admin password
podman exec -it -w /home/backend dmart /home/venv/bin/python3.11 ./set_admin_passwd.py

# Load the sample spaces data
podman exec -it -w /home/backend dmart bash -c 'source /home/venv/bin/activate && ./reload.sh'

# Run the auto tests 
podman exec -it -w /home/backend dmart ./curl.sh

# Open the browser to login to the admin tool and click on login. 
# User name: dmart
# Password: The password you entered in the set_admin_passwd step above.
# Url : http://localhost:8000

```

### Manual (for advanced users)
#### Requirements

- git
- jq
- python == 3.11
- pip
- redis >= 7.2
- RedisJSON (rejson) >= 2.6
- RediSearch >= 2.8
- python venv


### Steps 

```bash

# Enable kefahi dnf from copr to download redis modules
sudo dnf copr enable kefah/RediSearch

# Download necessary system packages
sudo dnf install jq redis rejson redisearch python3-pip python3
echo 'loadmodule /usr/lib64/redis/modules/librejson.so
loadmodule /usr/lib64/redis/modules/redisearch.so' | sudo tee -a /etc/redis/redis.conf
sudo systemctl start redis


git clone https://github.com/edraj/dmart.git

cd dmart 

# Make logs folder
mkdir logs

# Copy sample spaces structure
cp -a sample/spaces ../


cd backend

# Create the virtual env
python -m venv env

# Activate virtual env
source env/bin/activate

# Install python modules
pip install --user -r requirements.txt

# Optionally, fine-tune your configuration
cp config.env.sample config.env

# Set the admin password
./set_admin_passwd.py

# Start DMART microservice
./main.py


# Optionally: check admin folder for systemd scripts

```

#### Automated testing

#### Installing python dependencies

```bash
pip install --user -r test-requirements.txt
```

#### Running

```bash
cd backend
./curl.sh
python -m pytest
```

<img class="center" src={CLITest} width="300">
<img class="center" src={PYTest} width="450">


#### Using the Admin UI tool

DMART has a comprehensive Admin UI that interacts with the backend entirely via the formal API. It is built with Svelte, Routify3 and SvelteStrap.

```bash
cd dmart/frontend
yarn install

# Configure the dmart server backend url in src/config.ts

# To run in Development mode
yarn dev

# To build and run in production / static file serving mode (i.e. w/o nodejs) using Caddy
yarn build
caddy run
```

### Building tauri binary (Linux AppImage)

This allows packaging the admin tool as a desktop application.

```
# Regular build without inspection
yarn tauri build --bundles appimage

# To add inspection (right mouse click -> inspect)
yarn tauri build --bundles appimage --debug

```

<img class="center" src={AdminUI1}>
<img class="center" src={AdminUI2}>

### Using the command line tool

DMART comes with a command line tool that can run from anywhere. It communicates with DMART over the api.

```bash
cd cli

# Create config.ini with proper access details (url, credentials ...etc)
cp config.ini.sample config.ini

# Install additional packages
pip install --user  -r requirements.txt

# Start the cli tool
./cli.py
```

<img class="center" src={CLI} width="450">
