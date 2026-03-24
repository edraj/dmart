import { writable } from "svelte/store";
import { website } from "@/config";

export interface NavbarTheme {
    type: "solid" | "gradient" | "custom-solid" | "custom-gradient";
    value: string;
}

const STORAGE_KEY = "cxb_navbar_theme";

function loadFromStorage(): NavbarTheme | null {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) return JSON.parse(raw);
    } catch {
        // ignore
    }
    return null;
}

function getConfigDefault(): NavbarTheme | null {
    if (website.theme?.type && website.theme?.value) {
        return { type: website.theme.type, value: website.theme.value };
    }
    return null;
}

function saveToStorage(theme: NavbarTheme | null) {
    if (theme) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(theme));
    } else {
        localStorage.removeItem(STORAGE_KEY);
    }
}

const initial = loadFromStorage() ?? getConfigDefault();
export const navbarTheme = writable<NavbarTheme | null>(initial);

navbarTheme.subscribe((val) => saveToStorage(val));

export function setNavbarTheme(type: NavbarTheme["type"], value: string) {
    navbarTheme.set({ type, value });
}

export function clearNavbarTheme() {
    navbarTheme.set(getConfigDefault());
}

/** Returns true if the background is dark enough to need white text */
export function isDarkBackground(theme: NavbarTheme | null): boolean {
    if (!theme) return false;
    // For gradients, check the first color
    const hex = theme.value.match(/#([0-9a-fA-F]{6})/);
    if (!hex) return true; // assume dark for unknown
    const r = parseInt(hex[1].substring(0, 2), 16);
    const g = parseInt(hex[1].substring(2, 4), 16);
    const b = parseInt(hex[1].substring(4, 6), 16);
    // Perceived luminance formula
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance < 0.55;
}

