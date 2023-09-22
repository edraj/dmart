import {login, logout, get_profile, query, QueryType, request, RequestType} from "./index";

// require('util').inspect.defaultOptions.depth = 10;

(async () => {
  // await login("alibaba", "abc");
  const out = await login("dmart", "Password1234");
  console.log(out);
  //console.log(JSON.stringify(out, undefined, 2));
  //console.dir(out, { depth: 5 })

  //console.log(out);
  const profile = await get_profile();
  //console.log(JSON.stringify(profile, undefined, 2));
  //const query_resp = await query({type: QueryType.search, space_name: "management", subpath: "/users", search: ""});
  const query_resp = await query({type: QueryType.search, space_name: "eser", subpath: "/arabic", search: "", retrieve_attachments: true, retrieve_json_payload: true, limit: 1});
  //console.log(JSON.stringify(query_resp, undefined, 2));
  console.log(query_resp);
  const request_resp = await request({space_name: "personal", request_type: RequestType.create, records: [] });
  await logout();
  console.log(profile, query_resp); // , request_resp);

})();
