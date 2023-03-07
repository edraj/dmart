import { writable } from "svelte/store";

const default_space = {
  space_name: "management",
  backend: "https://api.dmart.cc",
  languages: { en: "English" },
  description: "Example of using the platform",
  displayname: "Demo space",
  shortname: "management",
};

let local;

if (!localStorage.getItem("active_space")) {
  localStorage.setItem("active_space", JSON.stringify(default_space));
}

local = JSON.parse(localStorage.getItem("active_space"));

const { subscribe, set } = writable(local);

function customSet(spacename) {
  set(spacename);
  localStorage.setItem("active_space", JSON.stringify(spacename));
}

export const active_space = {
  set: (value) => customSet(value),
  subscribe,
  reset: () => customSet(default_space),
};
