import dmart_fetch from "./fetch.js";
import { website } from "./config.js";
import { get } from "svelte/store";
import signedin_user from "./stores/signedin_user";
// import sha1 from "./sha1.js";

export async function dmart_list_schemas() {
  return await dmart_query({ type: "subpath", subpath: "schema" });
}

export async function dmart_login(username, password) {
  const browse_query = {
    shortname: username,
    password: password,
  };
  return await dmart_request("user/login", browse_query);
  //return { "records": [{ "displayname": "ali", "shortname": "hisense" }] };//resp;
}

export async function dmart_create_folder(space_name, subpath, shortname) {
  const request = {
    space_name,
    request_type: "create",
    records: [
      {
        resource_type: "folder",
        subpath,
        shortname,
        attributes: { is_active: true },
      },
    ],
  };
  return dmart_request("managed/request", request);
}

export async function dmart_get_schemas(space_name, shortname) {
  const query = {
    space_name,
    type: "subpath",
    subpath: "/schema",
    retrieve_json_payload: true,
    filter_shortnames: [shortname],
  };
  return dmart_query(query);
}

export async function dmart_create_schemas(space_name, shortname, body) {
  const request = {
    space_name,
    request_type: "create",
    records: [
      {
        resource_type: "schema",
        shortname,
        subpath: "/schema",
        attributes: {
          is_active: true,
          payload: {
            content_type: "json",
            schema_shortname: "meta_schema",
            body,
          },
        },
      },
    ],
  };
  return dmart_request("managed/request", request);
}

export async function dmart_request(api_suburl, browse_query) {
  const browse_url = `${website.backend}/${api_suburl}`;
  const browse_headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    Connection: "close",
  };
  const browse_request = {
    method: "POST",
    headers: browse_headers,
    credentials: "include",
    cache: "no-cache",
    mode: "cors",
    body: JSON.stringify(browse_query),
  };
  return await dmart_fetch(browse_url, browse_request);
}

export async function dmart_query(query) {
  const browse_query = {
    request_type: "query",
    space_name: website.space_name,
    ...query,
  };
  //console.log("IMX query", browse_query);
  return dmart_request("managed/query", browse_query);
}

export async function dmart_spaces(query) {
  return dmart_request("managed/space", query);
}

export async function dmart_tags() {
  const query = {
    subpath: "/posts",
    resource_types: ["post"],
    query_type: "tags",
  };
  const json = await dmart_query(query);
  let tags = [];
  if (json.results[0].status == "success") {
    json.records[0].attributes.tags.forEach(function (record) {
      let one = {
        name: record.tag,
        frequency: record.frequency,
      };
      tags.push(one);
    });
  }
  return tags;
}

export async function dmart_pub_query(
  subpath,
  resource_types,
  resource_shortnames = [],
  query_type = "subpath",
  search = "*",
  limit = 10,
  offset = 0
) {
  const browse_url = `${website.backend}/query/${
    website.space_name
  }/${encodeURIComponent(
    subpath
  )}?query_type=${query_type}&search=${encodeURIComponent(
    search
  )}&resource_types=${resource_types}&resource_shortnames=${encodeURIComponent(
    resource_shortnames.join(",")
  )}&offset=${offset}&limit=${limit}`;
  const browse_headers = { Accept: "application/json", Connection: "close" };
  const browse_request = {
    method: "GET",
    headers: browse_headers,
    credentials: "include",
    cache: "no-cache",
    mode: "cors",
  };
  const json = await dmart_fetch(browse_url, browse_request);
  if (json.records) {
    json.records.forEach((record) => {
      if (record.attachments.media) {
        record.attachments.media.forEach((attachment) => {
          if (
            attachment.attributes.payload &&
            attachment.attributes.payload.filepath
          ) {
            attachment.url = `${website.backend}/media/${website.space_name}/${attachment.subpath}/${record.shortname}/${attachment.attributes.payload.filepath}`;
          }
        });
      }
    });
  }
  return json;
}

export async function dmart_pub_tags(
  subpath = "/posts",
  resource_types = ["post"]
) {
  const json = await dmart_pub_query(subpath, resource_types, [], "tags");
  let tags = [];
  if (json.results[0].status == "success") {
    json.records[0].attributes.tags.forEach(function (record) {
      let one = {
        name: record.tag,
        frequency: record.frequency,
      };
      tags.push(one);
    });
  }
  return tags;
}
export function dmart_entry_displayname(record) {
  return record?.attributes?.displayname?.en
    ? record.attributes.displayname.en
    : record.shortname;
}

export function dmart_attachment_url(attachment) {
  if (attachment.attributes.payload && attachment.attributes.payload.filepath) {
    return `${website.backend}/media/${website.space_name}/${attachment.subpath}/${attachment.shortname}/${attachment.attributes.payload.filepath}`;
  }
}

export async function dmart_entry(
  resource_type,
  space_name,
  subpath,
  shortname,
  schema_shortname,
  ext,
  content_type = "json"
) {
  const browse_request = {
    method: "GET",
    credentials: "include",
    cache: "no-cache",
    mode: "cors",
    headers: { "Content-Type": `application/${content_type}` },
  };
  return await dmart_fetch(
    `${website.backend}/managed/payload/${resource_type}/${space_name}/${subpath}/${shortname}.${schema_shortname}.${ext}`.replaceAll(
      "..",
      "."
    ),
    browse_request,
    content_type === "json" ? "json" : "blob"
  );
}

export async function dmart_entries(
  space,
  subpath,
  filter_types = [],
  filter_shortnames = [],
  query_type = "search",
  search = "",
  limit = 20,
  jq_filter = ""
) {
  const query = {
    space_name: space,
    subpath: subpath,
    filter_types,
    filter_shortnames,
    type: query_type,
    search: search,
    jq_filter: jq_filter,
  };
  if (limit) {
    query.limit = limit;
  }
  const json = await dmart_query(query);
  // console.log("JSON: ", json);
  let records = [];
  if (json.status == "success") {
    json.records.forEach(function (record) {
      /*
      for (const attachment_type in record.attachments) {
        //console.log("Attachment type: ", attachment_type);
        //console.log("Attachments of type: ", record.attachments[attachment_type]);
        record.attachments[attachment_type] = record.attachments[attachment_type].map(attachment => {
          if (attachment.attributes.payload && attachment.attributes.payload.filepath) {
            attachment.url = `${website.backend}/media/${website.space_name}/${attachment.subpath}/${record.shortname}/${attachment.attributes.payload.filepath}`;
          }
          return attachment;
        });
      }*/
      //record.displayname = record.attributes.displayname?record.attributes.displayname:record.shortname;
      record.displayname =
        record?.attributes?.displayname?.en || record.shortname;
      records.push(record);
    });
  }
  return records;
}

export async function dmart_pub_submit(
  interaction_type,
  subpath,
  parent_shortname = null,
  attributes = {}
) {
  //console.log("Record: ", record, "Intraction: ", interaction_type);
  let curruser = get(signedin_user).shortname || "anon";
  const request = {
    actor_shortname: curruser,
    space_name: website.space_name,
    request_type: "submit",
    records: [
      {
        resource_type: interaction_type,
        shortname: "dummy",
        subpath: subpath,
        attributes: attributes,
      },
    ],
  };

  if (parent_shortname) request.records[0].parent_shortname = parent_shortname;

  let formdata = new FormData();
  //console.log("Data: ", JSON.stringify(request));
  formdata.append("request", JSON.stringify(request));
  const browse_url = `${website.backend}/submit`;
  const browse_headers = { Accept: "application/json", Connection: "close" };
  const browse_request = {
    method: "POST",
    headers: browse_headers,
    credentials: "include",
    cache: "no-cache",
    mode: "cors",
    body: formdata,
  };
  return dmart_fetch(browse_url, browse_request);
}

export async function dmart_postmedia(record, upload) {
  const request = {
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: "create",
    records: [record],
  };
  let formdata = new FormData();
  //console.log("Data: ", JSON.stringify(request));
  formdata.append("request", JSON.stringify(request));
  formdata.append("file", upload);
  const browse_url = `${website.backend}/media`;
  const browse_headers = { Accept: "application/json", Connection: "close" };
  const browse_request = {
    method: "POST",
    headers: browse_headers,
    credentials: "include",
    cache: "no-cache",
    mode: "cors",
    body: formdata,
  };
  return dmart_fetch(browse_url, browse_request);
}

export async function dmart_content(action, record) {
  const request = {
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: action,
    records: [record],
  };
  return dmart_request(request);
}

export async function dmart_create_content(
  space_name,
  subpath,
  shortname,
  schema_shortname,
  body
) {
  const request = {
    space_name,
    request_type: "create",
    records: [
      {
        resource_type: "content",
        shortname,
        subpath,
        attributes: {
          payload: {
            content_type: "json",
            schema_shortname,
            body,
          },
        },
      },
    ],
  };
  return await dmart_request("managed/request", request);
}

export async function dmart_update_content(content) {
  content;
}

export async function dmart_delete_content(
  resource_type,
  subpath,
  shortname,
  parent_shortname = null
) {
  const request = {
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: "delete",
    records: [
      {
        resource_type: resource_type,
        subpath: subpath,
        shortname: shortname,
      },
    ],
  };

  if (parent_shortname) request.records[0].parent_shortname = parent_shortname;

  console.log("Delete request: ", request);
  let resp = await dmart_request(request);
  return resp.results[0];
}

export async function dmart_folder(
  space_name,
  subpath,
  schema_shortname,
  shortname
) {
  const request = {
    space_name,
    request_type: "create",
    records: [
      {
        resource_type: "folder",
        subpath,
        shortname,
        attributes: {
          is_active: true,
          payload: {
            content_type: "json",
            schema_shortname: "folder_rendering",
            body: {
              shortname_title: "Unique ID",
              content_schema_shortnames: [schema_shortname],
              index_attributes: [
                {
                  key: "shortname",
                  name: "Unique ID",
                },
                {
                  key: "created_at",
                  name: "Created At",
                },
                {
                  key: "owner_shortname",
                  name: "Created By",
                },
              ],
              allow_create: true,
              allow_update: true,
              allow_delete: true,
              use_media: true,
              expand_children: false,
              content_resource_types: ["content"],
              allow_upload_csv: true,
              allow_csv: true,
              filter: [],
            },
          },
        },
      },
    ],
  };
  return await dmart_request("managed/request", request);
}

export async function dmart_update_embedded(
  content_type,
  embedded,
  subpath,
  shortname,
  resource_type
) {
  let record = {
    subpath: subpath,
    shortname: shortname,
    resource_type: resource_type,
    attributes: {
      payload: {
        // checksum: `sha1:${sha1(embedded)}`,
        embedded: embedded,
        content_type: content_type, //"text/html; charset=utf8",
        bytesize: new Blob([embedded]).size,
      },
    },
  };

  let resp = await dmart_content("update", record);
  return resp.results[0];
}

/*
export async function dmart_rename(oldshortname, newshortname) { }
export async function dmart_copy(subpath, shortname, newsubpath) { }
export async function dmart_move(subpath, shortname, newsubpath) { }
*/
