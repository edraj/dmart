### **Installation and Setup Instructions**

---

**Container (recommended)**

Using podman (or docker), dmart can be fully setup and configured in few minutes.

You only need a command line console, git and podman (or docker).

**Steps**

```
# Clone the git repo
git clone https://github.com/edraj/dmart.git
cd dmart/admin_scripts/docker

# Build the container
podman build -t dmart -f Dockerfile

# Run the container
podman run --name dmart -p 8000:8000 -d -it dmart

# Set the admin password
podman exec -it -w /home/backend dmart /home/venv/bin/python3 ./set_admin_passwd.py

# Load the sample spaces data
podman exec -it -w /home/backend dmart bash -c 'source /home/venv/bin/activate && ./reload.sh'

# Run the auto tests
podman exec -it -w /home/backend dmart ./curl.sh

# Open the browser to login to the admin tool and click on login.
# User name: dmart
# Password: The password you entered in the set_admin_passwd step above.
# Url : http://localhost:8000

```

**Manual (for advanced users)**

**Requirements**

- git
- jq
- python >= 3.11
- pip
- redis >= 7.2
- RedisJSON (rejson) >= 2.6
- RediSearch >= 2.8
- python venv

**Steps**

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
