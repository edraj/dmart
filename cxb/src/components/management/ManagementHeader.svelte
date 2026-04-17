<script lang="ts">
    import {
        Avatar,
        Button,
        CloseButton,
        Drawer,
        Dropdown,
        DropdownDivider,
        DropdownItem,
    } from "flowbite-svelte";
    import {
        BarsOutline,
        FolderSolid,
        MoonOutline,
        OpenDoorOutline,
        SunOutline,
        UserSettingsSolid,
        UserSolid,
    } from "flowbite-svelte-icons";
    import { activeRoute, goto } from "@roxi/routify";
    import { signout, user } from "@/stores/user";
    import { getAvatar } from "@/lib/dmart_services";
    import { locale, switchLocale } from "@/i18n";
    import { website } from "@/config";
    import { theme } from "@/stores/theme.svelte";
    import { navbarTheme, isDarkBackground } from "@/stores/navbar_theme";

    $goto;

    let customBg = $derived($navbarTheme?.value);
    let onCustomDark = $derived(isDarkBackground($navbarTheme));

    type Tab = { href: string; match: string; label: string; icon: typeof FolderSolid };
    const tabs: Tab[] = [
        { href: "/management/content", match: "/management/content", label: "Spaces", icon: FolderSolid },
        { href: "/management/tools", match: "/management/tools", label: "Tools", icon: UserSettingsSolid },
    ];

    const langs = ["en", "ar", "ku"] as const;
    let availableLangs = $derived(langs.filter((l) => l in (website?.languages ?? {})));

    let avatarUrl: string | null = $state(null);
    let loadedShortname = "";
    $effect(() => {
        const shortname = $user.shortname ?? "";
        if (shortname && shortname !== loadedShortname) {
            loadedShortname = shortname;
            getAvatar(shortname)
                .then((url) => { avatarUrl = url; })
                .catch(() => { avatarUrl = null; });
        }
    });

    let drawerHidden = $state(true);

    function setLanguage(lang: string) {
        switchLocale(lang);
    }

    function goToProfile(e: Event) {
        e.preventDefault();
        e.stopPropagation();
        $goto("/management/profile");
    }

    function logout(e: Event) {
        e.preventDefault();
        e.stopPropagation();
        signout();
    }

    function navigate(href: string) {
        drawerHidden = true;
        $goto(href);
    }

    function isActive(match: string) {
        return $activeRoute.url.includes(match);
    }
</script>

<div
    class="flex items-center justify-between border-b px-5 transition-colors"
    class:border-[color:var(--color-border)]={!customBg}
    class:border-transparent={!!customBg}
    class:bg-[color:var(--color-bg)]={!customBg}
    class:on-custom-dark={onCustomDark}
    style:background={customBg}
>
    <!-- Desktop tabs -->
    <ul class="hidden md:flex flex-row gap-8 me-auto" aria-label="Primary">
        {#each tabs as tab}
            {@const Icon = tab.icon}
            {@const current = isActive(tab.match)}
            <li class="relative">
                <a
                    href={tab.href}
                    onclick={(e) => { e.preventDefault(); navigate(tab.href); }}
                    aria-current={current ? "page" : undefined}
                    class="flex items-center gap-1 my-3 text-[color:var(--color-text)] aria-[current=page]:text-primary hover:text-primary transition-colors"
                >
                    <Icon size="md" />
                    <span class="mx-1">{tab.label}</span>
                </a>
                {#if current}
                    <div class="absolute bottom-0 start-0 end-0 h-1 bg-primary rounded-t"></div>
                {/if}
            </li>
        {/each}
    </ul>

    <!-- Mobile hamburger -->
    <button
        type="button"
        class="md:hidden p-2 text-[color:var(--color-text)] me-auto"
        aria-label="Open navigation menu"
        onclick={() => (drawerHidden = false)}
    >
        <BarsOutline size="md" />
    </button>

    <div class="flex items-center gap-3">
        <!-- Language switcher -->
        {#if availableLangs.length > 1}
            <div
                class="inline-flex rounded-full bg-[color:var(--color-surface)] p-1"
                role="tablist"
                aria-label="Language"
            >
                {#each availableLangs as lang}
                    <button
                        type="button"
                        role="tab"
                        aria-selected={$locale === lang}
                        class="w-8 h-8 flex items-center justify-center rounded-full text-sm font-medium transition-all
                            aria-selected:bg-[color:var(--color-bg)]
                            aria-selected:border-2 aria-selected:border-primary aria-selected:shadow-sm
                            text-[color:var(--color-text-muted)] aria-selected:text-primary hover:text-primary"
                        onclick={() => setLanguage(lang)}
                    >
                        {lang.toUpperCase()}
                    </button>
                {/each}
            </div>
        {/if}

        <!-- Dark-mode toggle -->
        <button
            type="button"
            class="w-9 h-9 flex items-center justify-center rounded-full bg-[color:var(--color-surface)] hover:bg-[color:var(--color-surface-hover)] text-[color:var(--color-text)] transition-colors"
            aria-label={theme.resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-pressed={theme.resolved === "dark"}
            onclick={() => theme.toggle()}
        >
            {#if theme.resolved === "dark"}
                <SunOutline size="sm" />
            {:else}
                <MoonOutline size="sm" />
            {/if}
        </button>

        <Button
            pill
            color="light"
            class="flex items-center gap-2 py-1 px-3"
            id="avatar_with_name"
        >
            <Avatar src={avatarUrl ?? undefined} size="xs" class="ring-2 ring-white" />
            <span class="text-sm">{$user.shortname}</span>

            <Dropdown simple triggeredBy="#avatar_with_name">
                <DropdownItem onclick={(e) => goToProfile(e)}>
                    <div class="flex items-center gap-2">
                        <UserSolid size="sm" /> My Profile
                    </div>
                </DropdownItem>
                <DropdownDivider />
                <DropdownItem onclick={(e) => logout(e)}>
                    <div class="flex items-center gap-2 text-red-600">
                        <OpenDoorOutline size="sm" /> Logout
                    </div>
                </DropdownItem>
            </Dropdown>
        </Button>
    </div>
</div>

<!-- Mobile navigation drawer -->
<Drawer
    placement="left"
    bind:hidden={drawerHidden}
    id="management-nav-drawer"
    class="bg-[color:var(--color-bg)]"
>
    <div class="flex items-center justify-between mb-4">
        <h5 class="text-base font-semibold text-[color:var(--color-text)]">Menu</h5>
        <CloseButton onclick={() => (drawerHidden = true)} />
    </div>
    <nav aria-label="Primary mobile">
        <ul class="flex flex-col gap-1">
            {#each tabs as tab}
                {@const Icon = tab.icon}
                {@const current = isActive(tab.match)}
                <li>
                    <a
                        href={tab.href}
                        onclick={(e) => { e.preventDefault(); navigate(tab.href); }}
                        aria-current={current ? "page" : undefined}
                        class="flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2
                            text-[color:var(--color-text)]
                            hover:bg-[color:var(--color-surface-hover)]
                            aria-[current=page]:bg-[color:var(--color-primary-soft)]
                            aria-[current=page]:text-primary
                            transition-colors"
                    >
                        <Icon size="md" />
                        <span>{tab.label}</span>
                    </a>
                </li>
            {/each}
        </ul>
    </nav>
</Drawer>

<style>
    :global(.on-custom-dark a),
    :global(.on-custom-dark button[role="tab"]),
    :global(.on-custom-dark > button) {
        color: #ffffff;
    }
    :global(.on-custom-dark a[aria-current="page"]) {
        color: #ffffff;
    }
    :global(.on-custom-dark a[aria-current="page"] + div) {
        background: #ffffff;
    }
</style>
