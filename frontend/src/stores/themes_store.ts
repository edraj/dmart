import { writable } from "svelte/store";

const theme = localStorage.getItem("theme") || "default";
export const themesStore = writable({
    rtlUrl: `./../../assets/themes/${theme}/bootstrap.rtl.min.css`,
    ltrUrl: `./../../assets/themes/${theme}/bootstrap.min.css`
});

export const themesList = [
    "default", "cosmo", "sandstone", "solar", "spacelab", "united"
]

export function handleThemeChange(e){
    const t = e.target.name;
    localStorage.setItem("theme", t);
    themesStore.set({
        rtlUrl: `./../../assets/themes/${t}/bootstrap.rtl.min.css`,
        ltrUrl: `./../../assets/themes/${t}/bootstrap.min.css`
    });
}