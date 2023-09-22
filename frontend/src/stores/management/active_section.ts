import { writable } from "svelte/store";
import sections from "./sections.json";

// export type JSONObject = { [key: string]: JSON };
// export interface JSONArray extends Array<JSON> {};
// export type JSON = null | string | number | boolean | JSONArray | JSONObject;

/* export enum ChildType {
  component = "component",
  folder = "folder",
  link = "link"
};*/

export type Child = {
  type: string,
  name: string,
  icon?: string,
  subpath?: string,
  space_name?: string
};

export type Section = {
  name: string,
  icon: string,
  is_expandable?: boolean,
  children: Array<Child>
};

const default_section : Section = sections[2]; // Content
let local : Section;

if (!localStorage.getItem("active_section")) {
  localStorage.setItem("active_section", JSON.stringify(default_section));
}

local = JSON.parse(localStorage.getItem("active_section") || "{}") as Section;

const { subscribe, set } = writable(local);

function customSet(section : Section) {
  set(section);
  localStorage.setItem("active_section", JSON.stringify(section));
}

export const active_section = {
  set: (value: Section) => customSet(value),
  subscribe,
  reset: () => customSet(default_section),
};
