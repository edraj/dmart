import { writable } from "svelte/store";

const triggerRefreshListWritable = writable(null);
export const triggerRefreshList = {
  set: (value) => triggerRefreshListWritable.set(value),
  subscribe: triggerRefreshListWritable.subscribe,
};

const triggerSearchListWritable = writable(null);
export const triggerSearchList = {
  set: (value) => triggerSearchListWritable.set(value),
  subscribe: triggerSearchListWritable.subscribe,
};

const triggerSidebarSelectionWritable = writable(null);
export const triggerSidebarSelection = {
  set: (value) => triggerSidebarSelectionWritable.set(value),
  subscribe: triggerSidebarSelectionWritable.subscribe,
};
