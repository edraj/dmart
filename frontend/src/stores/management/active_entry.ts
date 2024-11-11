import { writable } from "svelte/store";
import {retrieve_entry, type ResponseEntry, ResourceType, ContentType} from "@/dmart";
import {string} from "svelte-jsonschema-form/dist/controls";

const default_value : ResponseEntry = {
  email: "",
  force_password_change: false,
  is_email_verified: false,
  is_msisdn_verified: false,
  is_open: false,
  msisdn: "",
  password: "",
  state: "",
  workflow_shortname: "",
  uuid: "",
  subpath: "",
  shortname: "",
  is_active: false,
  displayname: {en:"", ar:"", kd:""},
  description: {en:"", ar:"", kd:""},
  tags: new Set<string>(),
  created_at: "",
  updated_at: "",
  owner_shortname: "",
  payload: {
    content_type: ContentType.json,
    schema_shortname: "",
    checksum: "",
    body: "",
    last_validated: "",
    validation_status: "invalid"
  }
}; 

let local : ResponseEntry = default_value;
if (typeof localStorage !== 'undefined') 
  local = localStorage.getItem("active_entry") ? (JSON.parse(localStorage.getItem("active_entry")) as ResponseEntry): default_value;
const {subscribe, set} = writable( local );

export default {
  set: (value: ResponseEntry) => set(value),
  subscribe,
  load: async (resource_type : ResourceType, space_name: string, subpath: string, shortname: string) => {
    const value = await retrieve_entry(resource_type, space_name, subpath, shortname, true, true);
    // FIXME : incase of error reset    
    set(value);
  },
  reset: () => {
    set(default_value);
  },
  is_set: (value: ResponseEntry) => value.shortname,
};
