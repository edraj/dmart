
import subprocess, json
pipe = subprocess.Popen(['/bin/bash', '-c', 'grep export login_creds.sh | cut -f 2 -d "=" | tr -d "\'"'], stdout=subprocess.PIPE)
if pipe and pipe.stdout:
    print(pipe.stdout.read())
    # env = json.loads(pipe.stdout.read())
