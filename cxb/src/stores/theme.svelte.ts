const KEY = "cxb.theme";
type Mode = "light" | "dark" | "system";

function readStoredMode(): Mode {
    if (typeof localStorage === "undefined") return "system";
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" || v === "system" ? v : "system";
}

function prefersDark(): boolean {
    return typeof window !== "undefined"
        && typeof window.matchMedia === "function"
        && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

class ThemeController {
    mode = $state<Mode>(readStoredMode());
    systemDark = $state(prefersDark());
    resolved = $derived(
        this.mode === "system" ? (this.systemDark ? "dark" : "light") : this.mode,
    );

    constructor() {
        if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
            window
                .matchMedia("(prefers-color-scheme: dark)")
                .addEventListener("change", (e) => (this.systemDark = e.matches));
        }
        $effect.root(() => {
            $effect(() => {
                if (typeof document === "undefined") return;
                document.documentElement.classList.toggle("dark", this.resolved === "dark");
                document.documentElement.style.colorScheme = this.resolved;
                if (typeof localStorage !== "undefined") {
                    localStorage.setItem(KEY, this.mode);
                }
            });
        });
    }

    set(m: Mode) {
        this.mode = m;
    }

    toggle() {
        this.mode = this.resolved === "dark" ? "light" : "dark";
    }
}

export const theme = new ThemeController();
