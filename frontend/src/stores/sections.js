import { writable } from 'svelte/store';
import initial_sections from './sections.json';

let local_sections = initial_sections;
/*if (!localStorage.getItem("sections")) {
  localStorage.setItem("sections", JSON.stringify(initial_sections));
}
local_sections = JSON.parse(localStorage.getItem("sections"));*/


const { subscribe, set } = writable(local_sections);

const sections = {
  set: (value) => set(value),
  subscribe, 
  reset: () => set(initial_sections),
};

export default sections;
