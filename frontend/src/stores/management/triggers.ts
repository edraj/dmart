import { writable } from "svelte/store";

const triggerRefresh = writable(null);
export const refresh = {
  set: (value: string) => triggerRefresh.set(value),
  subscribe: triggerRefresh.subscribe,
};

const triggerSearch = writable("");
export const search = {
  set: (value: string) => triggerSearch.set(value),
  subscribe: triggerSearch.subscribe,
};

const triggerSidebar = writable(null);
export const triggerSidebarSelection = {
  set: (value: string) => triggerSidebar.set(value),
  subscribe: triggerSidebar.subscribe,
};
