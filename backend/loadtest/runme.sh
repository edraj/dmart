#!/bin/bash

which vegeta > /dev/null || ( echo "Can'd find vegeta, download and put on path : https://github.com/tsenart/vegeta"; exit )

API_URL="http://127.0.0.1:8282"
CT="Content-Type: application/json"

source ../login_creds.sh
declare -i RESULT=0


AUTH_TOKEN=$(curl -i -s -H "$CT" -d "$SUPERMAN" ${API_URL}/user/login  | grep set-cookie | sed 's/^[^=]*=\(.*\); Http.*$/\1/g')
RESULT+=$?
echo "Logged-in as super admin" >&2

cat <<EOF | vegeta attack -duration=10s | tee results.bin | vegeta report  # -type="json" | jq .

# Plain service api main point 
GET ${API_URL}

# Who am i
GET ${API_URL}/info/me
Authorization: Bearer ${AUTH_TOKEN}

# Get profile
GET ${API_URL}/user/profile
Authorization: Bearer ${AUTH_TOKEN}

# Update admin Email
POST ${API_URL}/managed/request
Content-Type: application/json
Authorization: Bearer ${AUTH_TOKEN}
@./update_user_email.json

# Reload security
GET ${API_URL}/managed/reload-security-data
Authorization: Bearer ${AUTH_TOKEN}

# Query spaces
POST ${API_URL}/managed/query
Content-Type: application/json
Authorization: Bearer ${AUTH_TOKEN}
@./query_spaces.json

# Server manifest
GET ${API_URL}/info/manifest
Authorization: Bearer ${AUTH_TOKEN}

# Export CSV
POST ${API_URL}/managed/csv
Content-Type: application/json
Authorization: Bearer ${AUTH_TOKEN}
@./export_csv.json

EOF

RESULT+=$?
echo "Sum of exit codes = ${RESULT}"

exit


+ echo -n -e 'Query spaces: \t\t\t'
Query spaces: 			++ jq -c -n '{space_name: "dummy", type: "spaces", subpath: "/"}'
+ RECORD='{"space_name":"dummy","type":"spaces","subpath":"/"}'
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","type":"spaces","subpath":"/"}' http://127.0.0.1:8282/managed/query
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create TLF folder: \t\t'
Create TLF folder: 		++ jq -c -n '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "myfolder", attributes:{tags: ["one","two"],     "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Schema Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}'
+ REQUEST='{"space_name":"dummy","request_type":"create","records":[{"resource_type":"folder","subpath":"/","shortname":"myfolder","attributes":{"tags":["one","two"],"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"},"payload":{"content_type":"json","schema_shortname":"folder_rendering","body":{"shortname_title":"Schema Shortname","content_schema_shortnames":["meta_schema"],"index_attributes":[{"key":"shortname","name":"Schema Shortname"}],"allow_create":false,"allow_update":false,"allow_delete":false,"use_media":false}}}}]}'
+ jq .status
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","request_type":"create","records":[{"resource_type":"folder","subpath":"/","shortname":"myfolder","attributes":{"tags":["one","two"],"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"},"payload":{"content_type":"json","schema_shortname":"folder_rendering","body":{"shortname_title":"Schema Shortname","content_schema_shortnames":["meta_schema"],"index_attributes":[{"key":"shortname","name":"Schema Shortname"}],"allow_create":false,"allow_update":false,"allow_delete":false,"use_media":false}}}}]}' http://127.0.0.1:8282/managed/request
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ SUBPATH=posts
+ echo -n -e 'Create posts folder: \t\t'
Create posts folder: 		++ jq -c -n --arg subpath / --arg shortname posts '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "posts", attributes:{tags: ["one","two"], is_active: true, "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Shortname", "content_schema_shortnames": ["content"], "index_attributes": [ { "key": "shortname", "name": "Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}'
+ REQUEST='{"space_name":"dummy","request_type":"create","records":[{"resource_type":"folder","subpath":"/","shortname":"posts","attributes":{"tags":["one","two"],"is_active":true,"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"},"payload":{"content_type":"json","schema_shortname":"folder_rendering","body":{"shortname_title":"Shortname","content_schema_shortnames":["content"],"index_attributes":[{"key":"shortname","name":"Shortname"}],"allow_create":false,"allow_update":false,"allow_delete":false,"use_media":false}}}}]}'
+ jq .status
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","request_type":"create","records":[{"resource_type":"folder","subpath":"/","shortname":"posts","attributes":{"tags":["one","two"],"is_active":true,"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"},"payload":{"content_type":"json","schema_shortname":"folder_rendering","body":{"shortname_title":"Shortname","content_schema_shortnames":["content"],"index_attributes":[{"key":"shortname","name":"Shortname"}],"allow_create":false,"allow_update":false,"allow_delete":false,"use_media":false}}}}]}' http://127.0.0.1:8282/managed/request
+ grep -q success
+ tee /dev/stderr
"success"
+ RESULT+=0
+ echo -n -e 'Create workflow folder: \t'
Create workflow folder: 	++ jq -c -n '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "workflows", attributes:{ "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Schema Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}'
+ REQUEST='{"space_name":"dummy","request_type":"create","records":[{"resource_type":"folder","subpath":"/","shortname":"workflows","attributes":{"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"},"payload":{"content_type":"json","schema_shortname":"folder_rendering","body":{"shortname_title":"Schema Shortname","content_schema_shortnames":["meta_schema"],"index_attributes":[{"key":"shortname","name":"Schema Shortname"}],"allow_create":false,"allow_update":false,"allow_delete":false,"use_media":false}}}}]}'
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","request_type":"create","records":[{"resource_type":"folder","subpath":"/","shortname":"workflows","attributes":{"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"},"payload":{"content_type":"json","schema_shortname":"folder_rendering","body":{"shortname_title":"Schema Shortname","content_schema_shortnames":["meta_schema"],"index_attributes":[{"key":"shortname","name":"Schema Shortname"}],"allow_create":false,"allow_update":false,"allow_delete":false,"use_media":false}}}}]}' http://127.0.0.1:8282/managed/request
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ SUBPATH=posts
+ echo -n -e 'Query folders: \t\t\t'
Query folders: 			++ jq -c -n '{ space_name: "dummy", type:"subpath", subpath: "/", }'
+ REQUEST='{"space_name":"dummy","type":"subpath","subpath":"/"}'
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","type":"subpath","subpath":"/"}' http://127.0.0.1:8282/managed/query
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create Schema for workflows: \t'
Create Schema for workflows: 	+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' 'request_type: "create"' -F 'request_record=@"../sample/test/createschemawork.json"' -F 'payload_file=@"../sample/test/workflow_schema.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create content for workflows: \t'
Create content for workflows: 	+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createticket.json"' -F 'payload_file=@"../sample/test/ticket_workflow.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create Schema for ticket: \t'
Create Schema for ticket: 	+ jq .status
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createschema.json"' -F 'payload_file=@"../sample/test/schema.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create QR Code: \t\t'
Create QR Code: 		++ mktemp
+ TEMP_FILE=/tmp/tmp.qvfYdr2DXT
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' --output /tmp/tmp.qvfYdr2DXT http://127.0.0.1:8282/qr/generate/ticket/dummy/myfolder/an_example

+ RESULT+=0
+ file -ib /tmp/tmp.qvfYdr2DXT
application/json; charset=us-ascii
+ rm -f /tmp/tmp.qvfYdr2DXT
+ echo -n -e 'Create ticket: \t\t\t'
Create ticket: 			+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' 'request_type: "create"' -F 'request_record=@"../sample/test/ticketcontent.json"' -F 'payload_file=@"../sample/test/ticketbody.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Move ticket: \t\t\t'
Move ticket: 			+ jq .status
+ curl -s -H 'Content-Type: application/json' -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -d '{"space_name": "dummy","request_type": "move","records": [{"resource_type": "ticket","subpath": "/myfolder","shortname": "an_example","attributes": {"src_subpath": "/myfolder","src_shortname": "an_example","dest_subpath": "/myfolder_new","dest_shortname": "an_example_new","is_active": true}}]}' http://127.0.0.1:8282/managed/request
+ tee /dev/stderr
+ grep -q success
"success"
+ echo -n -e 'Move back to old: \t\t'
Move back to old: 		+ jq .status
+ curl -s -H 'Content-Type: application/json' -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -d '{"space_name": "dummy","request_type": "move","records": [{"resource_type": "ticket","subpath": "/myfolder_new","shortname": "an_example_new","attributes": {"src_subpath": "/myfolder_new","src_shortname": "an_example_new","dest_subpath": "/myfolder","dest_shortname": "an_example","is_active": true}}]}' http://127.0.0.1:8282/managed/request
+ tee /dev/stderr
+ grep -q success
"success"
+ echo -n -e 'Lock ticket: \t\t\t'
Lock ticket: 			+ curl -s -X PUT -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' http://127.0.0.1:8282/managed/lock/ticket/dummy/myfolder/an_example
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ echo -n -e 'Unlock ticket: \t\t\t'
Unlock ticket: 			+ curl -s -X DELETE -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' http://127.0.0.1:8282/managed/lock/dummy/myfolder/an_example
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ echo -n -e 'Create Content: \t\t'
Create Content: 		++ jq -c -n --arg subpath posts --arg shortname 97326c47 '{ space_name: "dummy", request_type:"create", records: [{resource_type: "content", subpath: $subpath, shortname: $shortname, attributes:{payload: {body: {"message": "this content created from curl request for dummying"}, content_type: "json"}, tags: ["one","two"], "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}}}]}'
+ REQUEST='{"space_name":"dummy","request_type":"create","records":[{"resource_type":"content","subpath":"posts","shortname":"97326c47","attributes":{"payload":{"body":{"message":"this content created from curl request for dummying"},"content_type":"json"},"tags":["one","two"],"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"}}}]}'
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","request_type":"create","records":[{"resource_type":"content","subpath":"posts","shortname":"97326c47","attributes":{"payload":{"body":{"message":"this content created from curl request for dummying"},"content_type":"json"},"tags":["one","two"],"description":{"en":"dummy","ar":"dummy","kd":"dummy"},"displayname":{"en":"en","ar":"ar","kd":"kd"}}}]}' http://127.0.0.1:8282/managed/request
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create Schema: \t\t\t'
Create Schema: 			+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createschema.json"' -F 'payload_file=@"../sample/test/schema.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create content: \t\t'
Create content: 		+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createcontent.json"' -F 'payload_file=@"../sample/test/data.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Managed CSV: \t\t\t'
Managed CSV: 			+ curl -s -H 'accept: text/csv' -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","subpath":"myfolder","type":"subpath","retrieve_json_payload":true,"limit":5}' http://127.0.0.1:8282/managed/csv
+ xargs -0 echo
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Create content: \t\t'
Create content: 		+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createcontent.json"' -F 'payload_file=@"../sample/test/data.json"' http://127.0.0.1:8282/managed/resource_with_payload
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Update content: \t\t'
Update content: 		+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' --data-binary @../sample/test/updatecontent.json http://127.0.0.1:8282/managed/request
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Upload attachment: \t\t'
Upload attachment: 		+ jq .status
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createmedia.json"' -F 'payload_file=@"../sample/test/logo.jpeg"' http://127.0.0.1:8282/managed/resource_with_payload
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Delete content: \t\t'
Delete content: 		+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' --data-binary @../sample/test/deletecontent.json http://127.0.0.1:8282/managed/request
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Query content: \t\t\t'
Query content: 			++ jq -c -n --arg subpath posts '{space_name: "dummy", type: "subpath", subpath: $subpath}'
+ RECORD='{"space_name":"dummy","type":"subpath","subpath":"posts"}'
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","type":"subpath","subpath":"posts"}' http://127.0.0.1:8282/managed/query
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
+ echo -n -e 'Delete dummy space: \t\t'
Delete dummy space: 		++ jq -c -n '{ "space_name": "dummy", "request_type": "delete", "records": [{ "resource_type": "space", "subpath": "/", "shortname": "dummy","attributes": {} } ]}'
+ DELETE='{"space_name":"dummy","request_type":"delete","records":[{"resource_type":"space","subpath":"/","shortname":"dummy","attributes":{}}]}'
+ curl -s -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZXJuYW1lIjoiZG1hcnQifSwiZXhwaXJlcyI6MTY5Nzg3NjQwNy4zNjYzMzN9.Q9DRRLqruptZ7-NUtSDyNfTWJuQM_rmMIn5zqfayp0s' -H 'Content-Type: application/json' -d '{"space_name":"dummy","request_type":"delete","records":[{"resource_type":"space","subpath":"/","shortname":"dummy","attributes":{}}]}' http://127.0.0.1:8282/managed/space
+ jq .status
+ tee /dev/stderr
+ grep -q success
"success"
+ RESULT+=0
