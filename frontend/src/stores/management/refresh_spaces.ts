import { writable } from "svelte/store";
let refresh = writable<boolean>(false);

// A simple refresh store (variable) that is based on a toggeling boolean
export default {
  subscribe: refresh.subscribe,
  refresh: () => refresh.update(entry => entry = !entry)
} 
