import { writable } from "svelte/store";

const { subscribe, set } = writable(false);

export const triggerRefreshList = {
  set: (value) => set(value),
  subscribe,
  reset: () => customSet([]),
};
