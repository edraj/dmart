#!/bin/bash

API_URL="http://127.0.0.1:8282"
CT="Content-Type: application/json"
SHORTNAME="97326c47"

source ./login_creds.sh
declare -i RESULT=0

# echo -n -e "Create user: \t\t"
# CREATE=$(jq -c -n --arg shortname "$SHORTNAME" --arg msisdn "$MSISDN" --arg password "$PASSWORD" '{resource_type: "user", subpath: "users", shortname: $shortname, attributes:{password: $password, msisdn:$msisdn, invitation: "hello"}}')
# curl -s -H "$CT" -d "$CREATE" "${API_URL}/user/create?invitation=$INVITATION"  | jq .status

# #echo -n -e "Send OTP using MSISDN: \t"
# #curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"msisdn": "'${MSISDN}'"}' ${API_URL}/user/otp-request | jq .

# #echo -n -e "Confirm OTP using MSISDN: \t"
# #curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"msisdn": "'${MSISDN}'", "code": "'${OTP_CODE}'"}' ${API_URL}/user/otp-confirm | jq .

echo -n -e "Login with admin: \t\t" >&2
AUTH_TOKEN=$(curl -i -s -H "$CT" -d "$SUPERMAN" ${API_URL}/user/login | grep set-cookie | sed 's/^[^=]*=\(.*\); Http.*$/\1/g')
RESULT+=$?
echo "$AUTH_TOKEN" | cut -d '.' -f 1 | base64 -d | jq .typ >&2
RESULT+=$?
# curl -s -c mycookies.jar -H "$CT" -d "$LOGIN" ${API_URL}/user/login | jq .status

echo -n -e "Get profile: \t\t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" $API_URL/user/profile | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create user from admin: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"create","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{"roles": ["test_role"], "msisdn": "7895412658", "email": "dummy_unqiue@gmail.com"}}]}' ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "update user from admin: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"update","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{"roles": ["test_role"], "msisdn": "7895412658", "email": "dummy_unqiue@gmail.com"}}]}' ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Verify Email/msisdn admin side: " >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"update","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{"is_email_verified":true,"is_msisdn_verified":true}}]}' ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Reset user from admin side\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d $'{"shortname": "distributor"}' ${API_URL}/user/reset | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Delete user from admin: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"delete","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{}}]}' ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

#echo -n -e "Health check: \t\t\t"
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/health/management | jq .status | tee /dev/stderr | grep -q "success"
#RESULT+=$?

echo -n -e "Collection Contacts Query: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"type": "search","space_name": "management","subpath": "users","retrieve_json_payload": true,"search": "","retrieve_attachments": true}' ${API_URL}/managed/query | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

# echo -n -e "Saved Queries for Report"
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"attributes": {"limit": 10,"offcet": 0,"key_search": ""},"resource_type": "content","shortname": "info_service","subpath": "/reports"}' ${API_URL}/managed/excute/query/aftersales | jq

echo -n -e "JQ filter: \t\t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"type": "search","space_name": "applications","subpath": "/","filter_types": ["folder"],"search": "applications","jq_filter" : ".[].shortname_title"}' ${API_URL}/managed/query | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Reload security: \t\t" >&2
curl -s -b mycookies.jar -H "$CT" -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/reload-security-data | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Delete dummy space: \t\t" >&2
DELETE=$(jq -c -n '{ "space_name": "dummy", "request_type": "delete", "records": [{ "resource_type": "space", "subpath": "/", "shortname": "dummy","attributes": {} } ]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$DELETE" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
# RESULT+=$?

echo -n -e "Create a new space (dummy): \t" >&2
CREATE=$(jq -c -n '{ "space_name": "dummy", "request_type": "create", "records": [{ "resource_type": "space", "subpath": "/", "shortname": "dummy","attributes": {"hide_space": true} } ]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$CREATE" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Query spaces: \t\t\t" >&2
RECORD=$(jq -c -n '{space_name: "dummy", type: "spaces", subpath: "/"}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/query | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create TLF folder: \t\t" >&2
REQUEST=$(jq -c -n '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "myfolder", attributes:{tags: ["one","two"],     "description": {"en": "dummy","ar": "dummy","ku": "dummy"},"displayname" : {"en": "en","ar": "ar", "ku":"ku"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Schema Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?
SUBPATH="posts"

echo -n -e "Create posts folder: \t\t" >&2
REQUEST=$(jq -c -n --arg subpath "/" --arg shortname "posts" '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "posts", attributes:{tags: ["one","two"], is_active: true, "description": {"en": "dummy","ar": "dummy","ku": "dummy"},"displayname" : {"en": "en","ar": "ar", "ku":"ku"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Shortname", "content_schema_shortnames": ["content"], "index_attributes": [ { "key": "shortname", "name": "Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create workflow folder: \t" >&2
REQUEST=$(jq -c -n '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "workflows", attributes:{ "description": {"en": "dummy","ar": "dummy","ku": "dummy"},"displayname" : {"en": "en","ar": "ar", "ku":"ku"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Schema Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?
SUBPATH="posts"

echo -n -e "Query folders: \t\t\t" >&2
REQUEST=$(jq -c -n '{ space_name: "dummy", type:"subpath", subpath: "/", }')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/query | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create Schema for workflows: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' 'request_type: "create"' -F 'request_record=@"./test/createschemawork.json"' -F 'payload_file=@"./test/workflow_schema.json"' ${API_URL}/managed/resource_with_payload | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create content for workflows: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"./test/createticket.json"' -F 'payload_file=@"./test/ticket_workflow.json"' ${API_URL}/managed/resource_with_payload | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create Schema for ticket: \t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"./test/createschema.json"' -F 'payload_file=@"./test/schema.json"' ${API_URL}/managed/resource_with_payload | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

# echo -n -e "Create QR Code: \t\t" >&2
# TEMP_FILE=$(mktemp)
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" --output $TEMP_FILE ${API_URL}/qr/generate/ticket/dummy/myfolder/an_example # | jq .status | tee /dev/stderr | grep -q "success"
# RESULT+=$?
# file -ib $TEMP_FILE >&2
# rm -f $TEMP_FILE
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F  ${API_URL}/qr/generate/ticket/dummy/myfolder/an_example  | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Create ticket: \t\t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' 'request_type: "create"' -F 'request_record=@"./test/ticketcontent.json"' -F 'payload_file=@"./test/ticketbody.json"' ${API_URL}/managed/resource_with_payload | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Move ticket: \t\t\t" >&2
curl -s -H "$CT" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"space_name": "dummy","request_type": "move","records": [{"resource_type": "ticket","subpath": "/myfolder","shortname": "an_example","attributes": {"src_subpath": "/myfolder","src_shortname": "an_example","dest_subpath": "/myfolder_new","dest_shortname": "an_example_new", "src_space_name": "dummy", "dest_space_name": "dummy", "is_active": true}}]}' ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Move back to old: \t\t" >&2
curl -s -H "$CT" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"space_name": "dummy","request_type": "move","records": [{"resource_type": "ticket","subpath": "/myfolder_new","shortname": "an_example_new","attributes": {"src_subpath": "/myfolder_new","src_shortname": "an_example_new","dest_subpath": "/myfolder","dest_shortname": "an_example", "src_space_name": "dummy", "dest_space_name": "dummy","is_active": true}}]}' ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Lock ticket: \t\t\t" >&2
curl -s -X "PUT" -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/lock/ticket/dummy/myfolder/an_example | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Unlock ticket: \t\t\t" >&2
curl -s -X "DELETE" -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/lock/dummy/myfolder/an_example | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Create Content: \t\t" >&2
REQUEST=$(jq -c -n --arg subpath "$SUBPATH" --arg shortname "$SHORTNAME" '{ space_name: "dummy", request_type:"create", records: [{resource_type: "content", subpath: $subpath, shortname: $shortname, attributes:{payload: {body: {"message": "this content created from curl request for dummying"}, content_type: "json"}, tags: ["one","two"], "description": {"en": "dummy","ar": "dummy","ku": "dummy"},"displayname" : {"en": "en","ar": "ar", "ku":"ku"}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Create content: \t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"./test/createcontent.json"' -F 'payload_file=@"./test/data.json"' ${API_URL}/managed/resource_with_payload | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Comment on content: \t\t"
COMMENT_SHORTNAME="greatcomment"
COMMENT_SUBPATH="$SUBPATH/$SHORTNAME"
RECORD=$(jq -c -n --arg subpath "$COMMENT_SUBPATH" --arg shortname "$COMMENT_SHORTNAME" '{ space_name: "dummy", request_type:"create", records: [{resource_type: "comment", subpath: $subpath, shortname: $shortname, attributes:{body: "A comment insdie the content resource"}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Managed CSV: \t\t\t" >&2
curl -s -H "accept: text/csv" -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"dummy","subpath":"myfolder","type":"subpath","retrieve_json_payload":true,"limit":5}' ${API_URL}/managed/csv | wc -l | xargs -IN test N -ge 2 > /dev/null && echo '"success"'  #| xargs -0 echo | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Update content: \t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" --data-binary "@./test/updatecontent.json" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Upload attachment: \t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"./test/createmedia.json"' -F 'payload_file=@"./test/logo.jpeg"' ${API_URL}/managed/resource_with_payload | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Delete content: \t\t" >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" --data-binary "@./test/deletecontent.json" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Query content: \t\t\t" >&2
RECORD=$(jq -c -n --arg subpath "$SUBPATH" '{space_name: "dummy", type: "subpath", subpath: $subpath}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/query | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

#echo -n -e "reload redis data: \t\t"
#RECORD=$(jq -c -n --arg subpath "$SUBPATH" '{space_name: "dummy", for_schemas: ["dummy_schema"]}')
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/reload-redis-data | jq .status | tee /dev/stderr | grep -q "success"

#echo -n -e "Delete admin: \t\t"
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{}' $API_URL/user/delete | jq .status | tee /dev/stderr | grep -q "success"

echo -n -e "Delete dummy space: \t\t" >&2
DELETE=$(jq -c -n '{ "space_name": "dummy", "request_type": "delete", "records": [{ "resource_type": "space", "subpath": "/", "shortname": "dummy","attributes": {} } ]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$DELETE" ${API_URL}/managed/request | jq .status | tee /dev/stderr | grep -q "success"
RESULT+=$?

echo -n -e "Server manifest: " >&2
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" ${API_URL}/info/manifest | jq . >&2
RESULT+=$?

echo "Sum of exit codes = $RESULT" >&2
exit $RESULT
