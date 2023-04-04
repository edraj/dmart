#!/bin/sh

API_URL="http://127.0.0.1:8282"
CT="Content-Type: application/json"
SHORTNAME="97326c47"

source ./login_creds.sh

# echo -n -e "Create user: \t\t"
# CREATE=$(jq -c -n --arg shortname "$SHORTNAME" --arg msisdn "$MSISDN" --arg password "$PASSWORD" '{resource_type: "user", subpath: "users", shortname: $shortname, attributes:{password: $password, msisdn:$msisdn, invitation: "hello"}}')
# curl -s -H "$CT" -d "$CREATE" "${API_URL}/user/create?invitation=$INVITATION"  | jq .status

# echo -n -e "Login: \t\t\t"
# curl -s -H "$CT" -d "${ALIBABA}" ${API_URL}/user/login | jq
# AUTH_TOKEN=$(curl -i -s -H "$CT" -d "${ALIBABA}" ${API_URL}/user/login  | grep set-cookie | sed 's/^[^=]*=\(.*\); Http.*$/\1/g')
# echo " Auth : $AUTH_TOKEN"

# #echo -n -e "Send OTP using MSISDN: \t"
# #curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"msisdn": "'${MSISDN}'"}' ${API_URL}/user/otp-request | jq . 

# #echo -n -e "Confirm OTP using MSISDN: \t"
# #curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"msisdn": "'${MSISDN}'", "code": "'${OTP_CODE}'"}' ${API_URL}/user/otp-confirm | jq . 

# echo -n -e "Get profile: \t\t"
# #curl -s -H "$AUTH" -H "$CT" $API_URL/user/profile | jq .status
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" $API_URL/user/profile | jq .status

# echo -n -e "Update profile: \t"
# UPDATE=$(jq -c -n --arg shortname "$SHORTNAME" '{resource_type: "user", subpath: "users", shortname: $shortname, attributes:{displayname: {"en": "New display name", "ar": "arabic", "kd": "kd"}}}')
# #curl -s -H "$AUTH" -H "$CT" -d "$UPDATE" $API_URL/user/profile | jq .status
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$UPDATE" $API_URL/user/profile | jq .status

# echo -n -e "Get profile: \t\t"
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" $API_URL/user/profile | jq .status

# echo -n -e "Delete user: \t\t"
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{}' $API_URL/user/delete | jq .status

#echo -n -e "Create admin: \t\t"
#CREATE=$(jq -c -n --arg shortname "$SUPER_ADMIN_SHORTNAME" --arg displayname "$DISPLAYNAME"  --arg password "$SUPER_ADMIN_PASSWORD" '{resource_type: "user", subpath: "users", shortname: $shortname, attributes:{"roles":["admin"],displayname: $displayname, password: $password, invitation: "hello"}}')
#curl -s -H "$CT" -d "$CREATE" "${API_URL}/user/create?invitation=$INVITATION"  | jq .status

echo -n -e "Login with admin: \t\t"
AUTH_TOKEN=$(curl -i -s -H "$CT" -d "$SUPERMAN" ${API_URL}/user/login  | grep set-cookie | sed 's/^[^=]*=\(.*\); Http.*$/\1/g')
echo "$AUTH_TOKEN" | cut -d '.' -f 1| base64 -d | jq .typ
# curl -s -c mycookies.jar -H "$CT" -d "$LOGIN" ${API_URL}/user/login | jq .status

echo -n -e "Create user from admin: \t" 
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"create","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{"roles": ["distributor_admin"], "msisdn": "7895412658", "email": "dummy_unqiue@gmail.com"}}]}' ${API_URL}/managed/request | jq .status

echo -n -e "update user from admin: \t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"update","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{"roles": ["ros"], "msisdn": "7895412658", "email": "dummy_unqiue@gmail.com"}}]}' ${API_URL}/managed/request | jq .status
echo -n -e "Verify Email/msisdn admin side: "
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"update","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{"is_email_verified":true,"is_msisdn_verified":true}}]}' ${API_URL}/managed/request | jq .status

echo -n -e "Reset user from admin side\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d $'{"shortname": "distributor"}' ${API_URL}/user/reset | jq .status

echo -n -e "Delete user from admin: \t" 
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"management","request_type":"delete","records":[{"resource_type":"user","subpath":"users","shortname":"distributor","attributes":{}}]}' ${API_URL}/managed/request | jq .status

echo -n -e "Health check: \t\t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/health/management | jq .status


echo -n -e "Collection Contacts Query: \t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"type": "search","space_name": "ordering","subpath": "collections/contacts","retrieve_json_payload": true,"search": "","retrieve_attachments": true}' ${API_URL}/managed/query | jq .status

# echo -n -e "Saved Queries for Report"
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"attributes": {"limit": 10,"offcet": 0,"key_search": ""},"resource_type": "content","shortname": "info_service","subpath": "/reports"}' ${API_URL}/managed/excute/query/aftersales | jq 

echo -n -e "JQ filter: \t\t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"type": "search","space_name": "aftersales","subpath": "/tickets","filter_schema_names": ["rc_compensation","connect_disconnect","add_remove_vas"],"filter_types": ["ticket"],"search": "","jq_filter" : ".[].shortname"}' ${API_URL}/managed/query | jq .status


echo -n -e "Reload security: \t\t"
curl -s -b mycookies.jar -H "$CT" -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/reload-security-data  | jq .status

echo -n -e "Delete dummy space: \t\t"
DELETE=$(jq -c -n '{ "space_name": "dummy", "request_type": "delete", "records": [{ "resource_type": "space", "subpath": "/", "shortname": "dummy","attributes": {} } ]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$DELETE" ${API_URL}/managed/space  | jq .status

echo -n -e "Create a new space (dummy): \t"
CREATE=$(jq -c -n '{ "space_name": "dummy", "request_type": "create", "records": [{ "resource_type": "space", "subpath": "/", "shortname": "dummy","attributes": {"hide_space": true} } ]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$CREATE" ${API_URL}/managed/space  | jq .status


echo -n -e "Query spaces: \t\t\t"
RECORD=$(jq -c -n '{space_name: "dummy", type: "spaces", subpath: "/"}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/query  | jq .status

echo -n -e "Create TLF folder: \t\t"
REQUEST=$(jq -c -n '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "myfolder", attributes:{tags: ["one","two"],     "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Schema Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status
SUBPATH="posts"

echo -n -e "Create posts folder: \t\t"
REQUEST=$(jq -c -n --arg subpath "/" --arg shortname "posts"  '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "posts", attributes:{tags: ["one","two"], is_active: true, "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Shortname", "content_schema_shortnames": ["content"], "index_attributes": [ { "key": "shortname", "name": "Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status

echo -n -e "Create Schema folder: \t\t"
REQUEST=$(jq -c -n --arg subpath "/" --arg shortname "schema"  '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "schema", attributes:{tags: ["one","two"], is_active: true, "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}') 
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status

echo -n -e "Create workflow folder: \t"
REQUEST=$(jq -c -n '{ space_name: "dummy", request_type:"create", records: [{resource_type: "folder", subpath: "/", shortname: "workflows", attributes:{ "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}, "payload": { "content_type": "json", "schema_shortname": "folder_rendering", "body": { "shortname_title": "Schema Shortname", "content_schema_shortnames": ["meta_schema"], "index_attributes": [ { "key": "shortname", "name": "Schema Shortname" }], "allow_create": false, "allow_update": false, "allow_delete": false, "use_media": false }}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status
SUBPATH="posts"

echo -n -e "Query folders: \t\t\t"
REQUEST=$(jq -c -n  '{ space_name: "dummy", type:"subpath", subpath: "/", }')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/query | jq .status



echo -n -e "Create Schema for workflows: \t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"'  'request_type: "create"' -F 'request_record=@"../sample/test/createschemawork.json"' -F 'payload_file=@"../sample/test/workflow_schema.json"' ${API_URL}/managed/resource_with_payload | jq .status


echo -n -e "Create content for workflows: \t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createticket.json"' -F 'payload_file=@"../sample/test/ticket_workflow.json"' ${API_URL}/managed/resource_with_payload  | jq .status


echo -n -e "Create Schema for ticket: \t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createschema.json"' -F 'payload_file=@"../sample/test/schema.json"' ${API_URL}/managed/resource_with_payload | jq .status

echo -n -e "Create ticket: \t\t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"'  'request_type: "create"' -F 'request_record=@"../sample/test/ticketcontent.json"' -F 'payload_file=@"../sample/test/ticketbody.json"' ${API_URL}/managed/resource_with_payload  | jq .status


echo -n -e "Create QR Code: \t\t"
TEMP_FILE=$(mktemp)
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" --output $TEMP_FILE  ${API_URL}/qr/generate/ticket/dummy/myfolder/an_example # | jq .status
file -ib $TEMP_FILE 
rm -f $TEMP_FILE 
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F  ${API_URL}/qr/generate/ticket/dummy/myfolder/an_example  | jq .status

# echo -n -e "Move / rename ticket: \t"
# curl -s -H "$CT" -H "Authorization: Bearer $AUTH_TOKEN"  -d '{"space_name": "dummy","request_type": "move","records": [{"resource_type": "ticket","subpath": "/myfolder/an_example","shortname": "'${SHORTNAME}'","attributes": {"src_subpath": "/tickets/postpaid_prime","src_shortname": "'${SHORTNAME}'","dest_subpath": "/tickets/postpaid_prime","dest_shortname": "'${UPDATE_SHORTNAME}'","is_active": true}}]}' ${API_URL}/managed/request | jq .status

# echo -n -e "Move / rename ticket back to old shortname: \t"
# curl -s -H "$CT" -H "Authorization: Bearer $AUTH_TOKEN"  -d '{"space_name": "dummy","request_type": "move","records": [{"resource_type": "ticket","subpath": "/myfolder/an_example","shortname": "'${UPDATE_SHORTNAME}'","attributes": {"src_subpath": "/tickets/postpaid_prime","src_shortname": "'${UPDATE_SHORTNAME}'","dest_subpath": "/tickets/postpaid_prime","dest_shortname": "'${SHORTNAME}'","is_active": true}}]}' ${API_URL}/managed/request | jq .status

# echo -n -e "Lock profile: \t"
# curl -s -X "PUT" -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/lock/ticket/dummy/myfolder/an_example | jq .status

# echo -n -e "Unlock profile: \t"
# curl -s -X "DELETE" -H "Authorization: Bearer $AUTH_TOKEN" ${API_URL}/managed/lock/dummy/myfolder/an_example | jq .status


echo -n -e "Create Content: \t\t" 
REQUEST=$(jq -c -n --arg subpath "$SUBPATH" --arg shortname "$SHORTNAME"  '{ space_name: "dummy", request_type:"create", records: [{resource_type: "content", subpath: $subpath, shortname: $shortname, attributes:{payload: {body: "this content created from curl request for dummying", content_type: "json"}, tags: ["one","two"], "description": {"en": "dummy","ar": "dummy","kd": "dummy"},"displayname" : {"en": "en","ar": "ar", "kd":"kd"}}}]}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$REQUEST" ${API_URL}/managed/request | jq .status 


echo -n -e "Create Schema: \t\t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createschema.json"' -F 'payload_file=@"../sample/test/schema.json"' ${API_URL}/managed/resource_with_payload | jq .status

echo -n -e "Create content: \t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createcontent.json"' -F 'payload_file=@"../sample/test/data.json"' ${API_URL}/managed/resource_with_payload  | jq .status 


# echo -n -e "Comment on content: \t"
# COMMENT_SHORTNAME="greatcomment"
# COMMENT_SUBPATH="$SUBPATH/$SHORTNAME"
# RECORD=$(jq -c -n --arg subpath "$COMMENT_SUBPATH" --arg shortname "$COMMENT_SHORTNAME"  '{ space_name: "dummy", request_type:"create", records: [{resource_type: "comment", subpath: $subpath, shortname: $shortname, attributes:{body: "A comment insdie the content resource"}}]}')
# curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/request | jq 

echo -n -e "Managed CSV: \t\t\t"
curl -s -H "accept: text/csv" -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{"space_name":"dummy","subpath":"myfolder","type":"subpath","retrieve_json_payload":true,"limit":5}' ${API_URL}/managed/csv | xargs -0 echo | jq .status


echo -n -e "Create content: \t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createcontent.json"' -F 'payload_file=@"../sample/test/data.json"' ${API_URL}/managed/resource_with_payload  | jq  .status

echo -n -e "Update content: \t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" --data-binary "@../sample/test/updatecontent.json" ${API_URL}/managed/request  | jq  .status

echo -n -e "Delete content: \t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" --data-binary "@../sample/test/deletecontent.json" ${API_URL}/managed/request  | jq  .status

echo -n -e "Upload attachment: \t\t"
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -F 'space_name="dummy"' -F 'request_record=@"../sample/test/createmedia.json"' -F 'payload_file=@"../sample/test/logo.jpeg"' ${API_URL}/managed/resource_with_payload  | jq .status

echo -n -e "Query content: \t\t\t"
RECORD=$(jq -c -n --arg subpath "$SUBPATH" '{space_name: "dummy", type: "subpath", subpath: $subpath}')
curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/query | jq .status

#echo -n -e "reload redis data: \t\t"
#RECORD=$(jq -c -n --arg subpath "$SUBPATH" '{space_name: "dummy", for_schemas: ["dummy_schema"]}')
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d "$RECORD" ${API_URL}/managed/reload-redis-data | jq .status

#echo -n -e "Delete admin: \t\t"
#curl -s -H "Authorization: Bearer $AUTH_TOKEN" -H "$CT" -d '{}' $API_URL/user/delete | jq .status
