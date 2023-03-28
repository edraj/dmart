import { writable } from "svelte/store";
import sections from "./sections.json";

const default_section = sections[1]; // Dashboard
let local;

if (!localStorage.getItem("active_section")) {
  localStorage.setItem("active_section", JSON.stringify(default_section));
}

local = JSON.parse(localStorage.getItem("active_section"));

const {subscribe, set} = writable(local);

function customSet(section) {
  set(section);
  localStorage.setItem("active_section", JSON.stringify(section));
}

export const active_section = {
  set: (value) => customSet(value),
  subscribe,
  reset: () => customSet(default_section),
};
