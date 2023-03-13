import { writable } from "svelte/store";

const local = JSON.parse(localStorage.getItem("selected_subpath"));
const { subscribe, set } = writable(local);

function customSet(subpathShortname) {
  set(subpathShortname);
  localStorage.setItem("selected_subpath", JSON.stringify(subpathShortname));
}

const selectedSubpath = {
  set: (value) => customSet(value),
  subscribe,
  reset: () => customSet([]),
};

export default selectedSubpath;
