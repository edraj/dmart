import { writable, get } from "svelte/store";
const init = {data:null};
const {set, update, subscribe} = writable(init);
export const has_changed = writable(false);

function customSet(new_value) {
  if ((! get(has_changed)) || confirm("Changes haven't been saved.\nDo you want to discard them?")) {
    has_changed.set(false); // Reset has_changed flag
    set(new_value);
  } else {
    console.log("Rejecting new active entry until the user saves changes");
  }
}

function customUpdate(new_entry) {
  let old = get(active_entry);
  console.log("Updating store from ... to", old, new_entry);
  return new_entry;
}

function updatePayload(new_entry, embedded_payload, previous_change_id) {
  //console.log("Updating payload to", embedded_payload, "new entry: ", new_entry);
  new_entry.data.attributes.payload.embedded = embedded_payload;
  new_entry.data.attributes.previous_change_id = previous_change_id;
  return new_entry;
}

export const active_entry = {
  set: (value) => customSet(value),
  updatePayload: (embedded_payload, previous_change_id) => update(entry => updatePayload(entry, embedded_payload, previous_change_id)),
  update: () => update(entry => customUpdate(entry)),
  subscribe,
  reset: () => customSet(init),
};

