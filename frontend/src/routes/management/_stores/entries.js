import { writable } from 'svelte/store';

let initial = {};

const { subscribe, set , update } = writable(initial);

export const entries = {
  set: (value) => set(value),
  subscribe,
  reset: () => set(initial),
  add: (subpath, entry) => update(entries => {
    if(!(subpath in entries)) {
      console.log("Creating new array for subpath", subpath);
      entries[subpath] = [];
    }
    // Remove if previously existed
    entries[subpath] = entries[subpath].filter((one) => { 
      if(one.data.shortname == entry.data.shortname) {
        console.log("Entry existed before. Deleting", one.data.shortname);
      }
      return one.data.shortname != entry.data.shortname;
    });
    // console.log("Entries before", entries);
    entries[subpath].push(entry);
    // console.log("Entries after", entries);
    return entries;
  }),
  del: (subpath, shortname) => update(entries => { 
    if(subpath in entries) {
      entries[subpath] = entries[subpath].filter(entry => shortname != entry.data.shortname);
    }
    return entries;
  }),
};
