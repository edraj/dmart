import { writable } from "svelte/store";

const { subscribe, set } = writable();

export const triggerRefreshList = {
  set: (value) => set(value),
  subscribe,
  reset: () => customSet([]),
};

export const triggerSearchList = {
  set: (value) => set(value),
  subscribe,
  reset: () => customSet([]),
};
