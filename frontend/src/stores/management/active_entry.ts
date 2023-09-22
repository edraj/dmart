import { writable } from "svelte/store";
import {retrieve_entry, ResponseEntry, ResourceType, ContentType} from "@/dmart";

const default_value : ResponseEntry = {
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

let local : ResponseEntry = localStorage.getItem("active_entry") ? (JSON.parse(localStorage.getItem("active_entry")) as ResponseEntry): default_value;
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
