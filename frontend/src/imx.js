import imx_fetch from '../custom-fetch.js';
import { website } from './space_config';
import { get } from 'svelte/store';
import signedin_user from './pages/managed/_stores/signedin_user';
import sha1 from "./sha1";

export async function imx_login(username, password) {
  const browse_query = { 
    request_type:"login",
    actor_shortname: username,
    space_name: website.space_name,
    auth_token: password
  };
  const resp = await imx_request(browse_query);
  //console.log( "Login response: ", resp);
  return resp;
}

async function imx_request(browse_query) {
  const browse_url = `${website.backend}/api`;
  const browse_headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Connection': 'close'};
  const browse_request = {
      method: 'POST',
      headers: browse_headers,
      credentials: 'include',
      cache: 'no-cache', 
      mode: 'cors',
      body: JSON.stringify(browse_query)
  };
  const json = await imx_fetch(browse_url, browse_request);
  return json;
}

export async function imx_query(query) {
  const browse_query = { "request_type":"query",
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    query: query
  };
  //console.log("IMX query", browse_query);
  return imx_request(browse_query);
}

export async function imx_tags() {
  const query = {
      "subpath":"/posts", 
      "resource_types": ["post"], 
      "query_type": "tags"
  };
  const json = await imx_query(query);
  let tags = []; 
  if(json.results[0].status == "success") {
    json.records[0].attributes.tags.forEach( function(record) {
      let one = {
        name: record.tag,
        frequency: record.frequency
      };  
      tags.push(one);
    });
  }
  return tags;
}

export async function imx_pub_query(subpath, resource_types, resource_shortnames = [], query_type = "subpath", search ="*", limit=10, offset=0) {
  const browse_url = `${website.backend}/query/${website.space_name}/${encodeURIComponent(subpath)}?query_type=${query_type}&search=${encodeURIComponent(search)}&resource_types=${resource_types}&resource_shortnames=${encodeURIComponent(resource_shortnames.join(','))}&offset=${offset}&limit=${limit}`;
  const browse_headers = {'Accept': 'application/json', 'Connection': 'close'};
  const browse_request = {
      method: 'GET',
      headers: browse_headers,
      credentials: 'include',
      cache: 'no-cache', 
      mode: 'cors'
  };
  const json = await imx_fetch(browse_url, browse_request);
  if(json.records) {
    json.records.forEach( record => {
      if(record.attachments.media) {
        record.attachments.media.forEach( attachment => {
          if(attachment.attributes.payload && attachment.attributes.payload.filepath) {
            attachment.url = `${website.backend}/media/${website.space_name}/${attachment.subpath}/${record.shortname}/${attachment.attributes.payload.filepath}`;
          }
        });
      }
    });
  }
  return json;
}

export async function imx_pub_tags(subpath="/posts", resource_types=["post"]) {
  const json = await imx_pub_query(subpath, resource_types, [], "tags");
  let tags = []; 
  if(json.results[0].status == "success") {
    json.records[0].attributes.tags.forEach( function(record) {
      let one = {
        name: record.tag,
        frequency: record.frequency
      };  
      tags.push(one);
    });
  }
  return tags;
}
export function imx_entry_displayname(record) {
  record.attributes.displayname?record.attributes.displayname:record.shortname;
}

export function imx_attachment_url(attachment) {
  if(attachment.attributes.payload && attachment.attributes.payload.filepath) {
    return `${website.backend}/media/${website.space_name}/${attachment.subpath}/${attachment.shortname}/${attachment.attributes.payload.filepath}`;
  }
}

export async function imx_entries(subpath, resource_types, resource_shortnames = [], query_type = "subpath", search ="", limit=20) {
  const query = { 
     "subpath":subpath, 
      "resource_types": resource_types, 
      "resource_shortnames": resource_shortnames, 
      query_type: query_type, 
      search: search 
    };
  if(limit) {
    query.limit = limit;
  }
  const json = await imx_query(query);
  // console.log("JSON: ", json);
  let records = []; 
  if(json.results[0].status == "success") {
    json.records.forEach( function(record) {
      for(const attachment_type in record.attachments) {
        //console.log("Attachment type: ", attachment_type);
        //console.log("Attachments of type: ", record.attachments[attachment_type]);
        record.attachments[attachment_type] = record.attachments[attachment_type].map( attachment => {
          if(attachment.attributes.payload && attachment.attributes.payload.filepath) {
            attachment.url = `${website.backend}/media/${website.space_name}/${attachment.subpath}/${record.shortname}/${attachment.attributes.payload.filepath}`;
          }
          return attachment;
        });
      }
      //record.displayname = record.attributes.displayname?record.attributes.displayname:record.shortname;
      record.displayname = record?.attributes?.displayname || record.shortname;
      records.push(record);
    });
  }
  return records;
}


export async function imx_pub_submit(interaction_type, subpath, parent_shortname=null, attributes = {}) {
  //console.log("Record: ", record, "Intraction: ", interaction_type);
  let curruser = get(signedin_user).shortname || "anon";
  const request = { 
    actor_shortname: curruser,
    space_name: website.space_name,
    request_type: "submit",
    records:[{
      resource_type: interaction_type,
      shortname: "dummy",
      subpath: subpath,
      attributes: attributes
    }]
  };

  if(parent_shortname)
    request.records[0].parent_shortname = parent_shortname;

  let formdata = new FormData();
  //console.log("Data: ", JSON.stringify(request));
  formdata.append("request", JSON.stringify(request));
  const browse_url = `${website.backend}/submit`;
  const browse_headers = {'Accept': 'application/json', 'Connection': 'close'};
  const browse_request = {
      method: 'POST',
      headers: browse_headers,
      credentials: 'include',
      cache: 'no-cache', 
      mode: 'cors',
      body: formdata
  };
  return imx_fetch(browse_url, browse_request);
}

export async function imx_postmedia(record, upload) {
  const request = { 
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: "create",
    records:[ record ]
  };
  let formdata = new FormData();
  //console.log("Data: ", JSON.stringify(request));
  formdata.append("request", JSON.stringify(request));
  formdata.append("file", upload);
  const browse_url = `${website.backend}/media`;
  const browse_headers = {'Accept': 'application/json', 'Connection': 'close'};
  const browse_request = {
      method: 'POST',
      headers: browse_headers,
      credentials: 'include',
      cache: 'no-cache', 
      mode: 'cors',
      body: formdata
  };
  return imx_fetch(browse_url, browse_request);
}

export async function imx_content(action, record) {
  const request = { 
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: action,
    records:[ record ]
  };
  return imx_request(request);
}

export async function imx_update_content(content) {
  content;
}

export async function imx_delete_content(resource_type, subpath, shortname, parent_shortname = null) {
  const request = { 
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: "delete",
    records:[
      {
        resource_type: resource_type,
        subpath: subpath,
        shortname: shortname
      }
    ]
  };

  if(parent_shortname)
    request.records[0].parent_shortname = parent_shortname;

  console.log("Delete request: ", request);
  let resp = await imx_request(request);
  return resp.results[0];
}

export async function imx_folder(action, subpath, shortname) {
  const request = { 
    actor_shortname: get(signedin_user).shortname,
    space_name: website.space_name,
    request_type: action,
    records:[
      {
        resource_type: "folder",
        subpath: subpath,
        shortname: shortname
      }
    ]
  };
  let resp = await imx_request(request);
  return resp.results[0];
}

export async function imx_update_embedded(content_type, embedded, subpath, shortname, resource_type) {
  let record = {
    subpath: subpath,
    shortname: shortname,
    resource_type: resource_type,
    attributes: {
      payload: {
        checksum: `sha1:${sha1(embedded)}`,
        embedded: embedded,
        content_type: content_type, //"text/html; charset=utf8",
        bytesize: new Blob([embedded]).size
      }
    }
  };

  let resp = await imx_content("update", record);
  return resp.results[0];
}

/*
export async function imx_rename(oldshortname, newshortname) { }
export async function imx_copy(subpath, shortname, newsubpath) { }
export async function imx_move(subpath, shortname, newsubpath) { }
*/


