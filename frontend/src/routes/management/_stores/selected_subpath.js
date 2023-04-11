import { writable } from "svelte/store";

const { subscribe, set } = writable({});

const selectedSubpath = {
  set: (value) => set(value),
  subscribe,
  reset: () => customSet([]),
};

export default selectedSubpath;
