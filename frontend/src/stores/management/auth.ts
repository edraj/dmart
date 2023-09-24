import { writable } from "svelte/store";
export const authToken = writable( typeof localStorage !== 'undefined' && localStorage.getItem("authToken") || "");
