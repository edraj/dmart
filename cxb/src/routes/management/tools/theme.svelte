<script lang="ts">
    import { goto } from "@roxi/routify";
    import {
        navbarTheme,
        setNavbarTheme,
        clearNavbarTheme,
    } from "@/stores/navbar_theme";
    import type { NavbarTheme } from "@/stores/navbar_theme";
    import { Button } from "flowbite-svelte";
    import {
        ArrowLeftOutline,
        PaletteOutline,
        CloseOutline,
        ClipboardOutline,
    } from "flowbite-svelte-icons";

    $goto;

    const solidPresets: { name: string; value: string }[] = [
        { name: "Midnight Navy", value: "#1B2A4A" },
        { name: "Volcanic Slate", value: "#2D3436" },
        { name: "Royal Indigo", value: "#4A00E0" },
        { name: "Emerald Night", value: "#0D7377" },
        { name: "Deep Rosewood", value: "#6B0F1A" },
    ];

    const gradientPresets: { name: string; value: string }[] = [
        {
            name: "Aurora Borealis",
            value: "linear-gradient(135deg, #0F2027, #203A43, #2C5364)",
        },
        {
            name: "Cosmic Voyager",
            value: "linear-gradient(135deg, #141E30, #243B55)",
        },
        {
            name: "Ember Horizon",
            value: "linear-gradient(135deg, #1A1A2E, #16213E, #0F3460)",
        },
        {
            name: "Velvet Dusk",
            value: "linear-gradient(135deg, #2C003E, #512DA8, #7C4DFF)",
        },
        {
            name: "Neon Mirage",
            value: "linear-gradient(135deg, #0D0D0D, #1A237E, #00BCD4)",
        },
    ];

    const gradientDirections = [
        { label: "To Right", value: "to right" },
        { label: "To Bottom Right", value: "to bottom right" },
        { label: "To Bottom", value: "to bottom" },
        { label: "To Bottom Left", value: "to bottom left" },
        { label: "To Left", value: "to left" },
    ];

    let customSolidColor = $state("#3C54F0");
    let gradientStart = $state("#141E30");
    let gradientEnd = $state("#243B55");
    let gradientDirection = $state("to right");

    function isActive(
        theme: NavbarTheme | null,
        type: string,
        value: string,
    ): boolean {
        return theme?.type === type && theme?.value === value;
    }

    function buildGradient(): string {
        return `linear-gradient(${gradientDirection}, ${gradientStart}, ${gradientEnd})`;
    }

    let copiedPreset = $state<string | null>(null);
    function copyThemeConfig(type: string, value: string, presetName: string) {
        const json = JSON.stringify({ type, value }, null, 4);
        const snippet = `"theme": ${json}`;
        navigator.clipboard.writeText(snippet);
        copiedPreset = presetName;
        setTimeout(() => {
            copiedPreset = null;
        }, 1500);
    }
</script>

<div class="container mx-auto p-8 max-w-4xl">
    <!-- Back button -->
    <button
        class="flex items-center gap-2 text-gray-600 hover:text-primary-600 mb-6 transition-colors"
        onclick={() => $goto("/management/tools")}
    >
        <ArrowLeftOutline size="sm" />
        <span>Back to Tools</span>
    </button>

    <div class="flex items-center gap-3 mb-8">
        <div class="p-3 bg-primary-100 rounded-full">
            <PaletteOutline class="w-8 h-8 text-primary-600" />
        </div>
        <div>
            <h1 class="text-2xl font-bold">Navbar Theme</h1>
            <p class="text-gray-500">Customize the navigation bar appearance</p>
        </div>
    </div>

    <!-- Solid Colors -->
    <section class="mb-10">
        <h2
            class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4"
        >
            Solid Colors
        </h2>
        <div class="grid grid-cols-5 gap-4">
            {#each solidPresets as preset}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div
                    class="group relative aspect-[3/2] rounded-xl shadow-sm border-2 transition-all duration-200 hover:scale-105 hover:shadow-lg cursor-pointer
                        {isActive($navbarTheme, 'solid', preset.value)
                        ? 'border-primary-500 ring-2 ring-primary-300 scale-105'
                        : 'border-transparent'}"
                    style:background={preset.value}
                    onclick={() => setNavbarTheme("solid", preset.value)}
                    title={preset.name}
                >
                    {#if isActive($navbarTheme, "solid", preset.value)}
                        <div
                            class="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-white flex items-center justify-center shadow"
                        >
                            <svg
                                class="w-3 h-3 text-primary-600"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="3"
                                    d="M5 13l4 4L19 7"
                                />
                            </svg>
                        </div>
                    {/if}
                    <button
                        class="absolute top-1.5 left-1.5 w-6 h-6 rounded-full bg-white/80 hover:bg-white flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                        title="Copy config.json snippet"
                        onclick={(e) => {
                            e.stopPropagation();
                            copyThemeConfig("solid", preset.value, preset.name);
                        }}
                    >
                        {#if copiedPreset === preset.name}
                            <svg
                                class="w-3 h-3 text-green-600"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                                ><path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="3"
                                    d="M5 13l4 4L19 7"
                                /></svg
                            >
                        {:else}
                            <ClipboardOutline class="w-3 h-3 text-gray-600" />
                        {/if}
                    </button>
                    <span
                        class="absolute bottom-0 left-0 right-0 text-center text-[11px] font-medium text-white py-1.5 bg-black/30 rounded-b-xl backdrop-blur-sm"
                    >
                        {preset.name}
                    </span>
                </div>
            {/each}
        </div>
    </section>

    <!-- Gradient Colors -->
    <section class="mb-10">
        <h2
            class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4"
        >
            Gradient Colors
        </h2>
        <div class="grid grid-cols-5 gap-4">
            {#each gradientPresets as preset}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div
                    class="group relative aspect-[3/2] rounded-xl shadow-sm border-2 transition-all duration-200 hover:scale-105 hover:shadow-lg cursor-pointer
                        {isActive($navbarTheme, 'gradient', preset.value)
                        ? 'border-primary-500 ring-2 ring-primary-300 scale-105'
                        : 'border-transparent'}"
                    style:background={preset.value}
                    onclick={() => setNavbarTheme("gradient", preset.value)}
                    title={preset.name}
                >
                    {#if isActive($navbarTheme, "gradient", preset.value)}
                        <div
                            class="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-white flex items-center justify-center shadow"
                        >
                            <svg
                                class="w-3 h-3 text-primary-600"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="3"
                                    d="M5 13l4 4L19 7"
                                />
                            </svg>
                        </div>
                    {/if}
                    <button
                        class="absolute top-1.5 left-1.5 w-6 h-6 rounded-full bg-white/80 hover:bg-white flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                        title="Copy config.json snippet"
                        onclick={(e) => {
                            e.stopPropagation();
                            copyThemeConfig(
                                "gradient",
                                preset.value,
                                preset.name,
                            );
                        }}
                    >
                        {#if copiedPreset === preset.name}
                            <svg
                                class="w-3 h-3 text-green-600"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                                ><path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="3"
                                    d="M5 13l4 4L19 7"
                                /></svg
                            >
                        {:else}
                            <ClipboardOutline class="w-3 h-3 text-gray-600" />
                        {/if}
                    </button>
                    <span
                        class="absolute bottom-0 left-0 right-0 text-center text-[11px] font-medium text-white py-1.5 bg-black/30 rounded-b-xl backdrop-blur-sm"
                    >
                        {preset.name}
                    </span>
                </div>
            {/each}
        </div>
    </section>

    <!-- Custom Pickers -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
        <!-- Custom Solid -->
        <section class="border border-gray-200 rounded-xl p-5">
            <h2
                class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4"
            >
                Custom Color
            </h2>
            <div class="flex items-center gap-4">
                <label class="relative cursor-pointer">
                    <input
                        type="color"
                        class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                        bind:value={customSolidColor}
                    />
                    <div
                        class="w-12 h-12 rounded-xl border-2 border-gray-300 shadow-sm transition-all hover:scale-110"
                        style:background={customSolidColor}
                    ></div>
                </label>
                <div class="flex-1">
                    <span class="text-sm font-mono text-gray-500"
                        >{customSolidColor}</span
                    >
                </div>
                <Button
                    size="sm"
                    color="light"
                    class="border-primary-300 text-primary-600 hover:bg-primary-50"
                    onclick={() =>
                        setNavbarTheme("custom-solid", customSolidColor)}
                >
                    Apply
                </Button>
            </div>
        </section>

        <!-- Custom Gradient -->
        <section class="border border-gray-200 rounded-xl p-5">
            <h2
                class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4"
            >
                Custom Gradient
            </h2>
            <div class="flex items-center gap-3 mb-3">
                <label class="relative cursor-pointer">
                    <input
                        type="color"
                        class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                        bind:value={gradientStart}
                    />
                    <div
                        class="w-10 h-10 rounded-lg border-2 border-gray-300 shadow-sm transition-all hover:scale-110"
                        style:background={gradientStart}
                    ></div>
                </label>
                <span class="text-gray-400">→</span>
                <label class="relative cursor-pointer">
                    <input
                        type="color"
                        class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                        bind:value={gradientEnd}
                    />
                    <div
                        class="w-10 h-10 rounded-lg border-2 border-gray-300 shadow-sm transition-all hover:scale-110"
                        style:background={gradientEnd}
                    ></div>
                </label>
                <select
                    class="flex-1 text-sm border border-gray-300 rounded-lg px-2 py-2"
                    bind:value={gradientDirection}
                >
                    {#each gradientDirections as dir}
                        <option value={dir.value}>{dir.label}</option>
                    {/each}
                </select>
            </div>
            <div class="flex items-center gap-3">
                <div
                    class="flex-1 h-8 rounded-lg border border-gray-200"
                    style:background={buildGradient()}
                ></div>
                <Button
                    size="sm"
                    color="light"
                    class="border-primary-300 text-primary-600 hover:bg-primary-50"
                    onclick={() =>
                        setNavbarTheme("custom-gradient", buildGradient())}
                >
                    Apply
                </Button>
            </div>
        </section>
    </div>

    <!-- Reset -->
    {#if $navbarTheme}
        <div class="flex justify-center">
            <Button
                color="light"
                class="flex items-center gap-2 text-red-600 border-red-200 hover:bg-red-50"
                onclick={() => clearNavbarTheme()}
            >
                <CloseOutline size="sm" />
                Reset to Default
            </Button>
        </div>
    {/if}
</div>
