<script lang="ts">
    import { InboxOutline } from "flowbite-svelte-icons";
    import type { Component, Snippet } from "svelte";

    let {
        icon,
        title = "No records found",
        hint,
        children,
    }: {
        icon?: Component<any>;
        title?: string;
        hint?: string;
        children?: Snippet;
    } = $props();

    const Icon = $derived(icon ?? InboxOutline);
</script>

<div
    class="flex flex-col items-center justify-center text-center py-12 px-6 rounded-[var(--radius-lg)] border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)]"
>
    <div
        class="w-14 h-14 mb-3 rounded-full flex items-center justify-center bg-[color:var(--color-primary-soft)] text-primary"
    >
        <Icon size="lg" />
    </div>
    <h3 class="text-base font-semibold text-[color:var(--color-text)]">{title}</h3>
    {#if hint}
        <p class="mt-1 text-sm text-[color:var(--color-text-muted)] max-w-md">{hint}</p>
    {/if}
    {#if children}
        <div class="mt-4">{@render children()}</div>
    {/if}
</div>
