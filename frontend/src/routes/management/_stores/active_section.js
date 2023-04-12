import { writable } from "svelte/store";

const { subscribe, set } = writable();

export const active_section = {
  set: (value) => set(value),
  subscribe,
  reset: () => customSet(),
};
