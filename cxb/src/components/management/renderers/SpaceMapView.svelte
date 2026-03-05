<script lang="ts">
    /**
     * SpaceMapView – renders a merged permission map as a tree:
     *
     *   📦 space_name
     *     📁 subpath
     *       Types:    content · folder · …
     *       Actions:  create · read · …
     *       Conditions: [json]
     *       Allowed Fields Values: {json}
     *       Filter Fields Values: "…"
     */

    type SubpathInfo = {
        resource_types: string[];
        actions: string[];
        conditions: string[];
        allowed_fields_values: Record<string, unknown>;
        filter_fields_values: string;
    };

    const {
        spaceMap = {},
        loading = false,
    }: {
        spaceMap: Record<string, Record<string, SubpathInfo>>;
        loading: boolean;
    } = $props();

    const ACTION_COLORS: Record<string, string> = {
        create: "bg-green-100 text-green-800",
        update: "bg-blue-100 text-blue-800",
        delete: "bg-red-100 text-red-800",
        query: "bg-cyan-100 text-cyan-800",
        view: "bg-cyan-100 text-cyan-800",
        replace: "bg-orange-100 text-orange-800",
        move: "bg-yellow-100 text-yellow-800",
        attach: "bg-lime-100 text-lime-800",
    };

    const CONDITION_COLORS: Record<string, string> = {
        own: "bg-yellow-100 text-yellow-800",
        is_active: "bg-yellow-100 text-yellow-800",
    };

    function actionColor(action: string): string {
        return ACTION_COLORS[action] ?? "bg-gray-100 text-gray-700";
    }

    function conditionColor(cond: string): string {
        return CONDITION_COLORS[cond] ?? "bg-yellow-100 text-yellow-800";
    }

    function pretty(v: unknown): string {
        return JSON.stringify(v, null, 2);
    }

    function isTruthy(v: unknown): boolean {
        if (v === null || v === undefined || v === "") return false;
        if (Array.isArray(v)) return v.length > 0;
        if (typeof v === "object") return Object.keys(v as object).length > 0;
        return Boolean(v);
    }

    function entries<T>(obj: Record<string, T>): [string, T][] {
        return Object.entries(obj);
    }
</script>

{#if loading}
    <div class="flex items-center gap-3 p-6 text-gray-500">
        <svg
            class="animate-spin h-5 w-5 text-blue-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
        >
            <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
            ></circle>
            <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
            ></path>
        </svg>
        <span>Loading permission map…</span>
    </div>
{:else if Object.keys(spaceMap).length === 0}
    <div class="p-6 text-center text-gray-400 border border-dashed rounded-lg">
        No space permissions found.
    </div>
{:else}
    <div class="space-y-4">
        {#each entries(spaceMap) as [space, subpathMap]}
            <div
                class="border border-gray-200 rounded-xl shadow-sm overflow-hidden"
            >
                <!-- Space header -->
                <div
                    class="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-200"
                >
                    <span class="text-xl">📦</span>
                    <span class="font-bold text-blue-800 text-base"
                        >{space}</span
                    >
                    <span class="ml-auto text-xs text-gray-400"
                        >{Object.keys(subpathMap).length} subpath{Object.keys(
                            subpathMap,
                        ).length !== 1
                            ? "s"
                            : ""}</span
                    >
                </div>

                <!-- Subpaths -->
                <div class="divide-y divide-gray-100">
                    {#each entries(subpathMap) as [subpath, info]}
                        <div class="px-5 py-3 space-y-1.5">
                            <div class="flex items-center gap-2">
                                <span class="text-base">📁</span>
                                <span
                                    class="font-mono text-sm font-semibold text-gray-700"
                                    >{subpath}</span
                                >
                            </div>

                            <!-- Resource types -->
                            {#if info.resource_types.length > 0}
                                <div
                                    class="flex flex-wrap items-center gap-1 ml-6"
                                >
                                    <span class="text-xs text-gray-400 mr-1"
                                        >Types:</span
                                    >
                                    {#each info.resource_types as rt}
                                        <span
                                            class="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded-full font-medium"
                                            >{rt}</span
                                        >
                                    {/each}
                                </div>
                            {/if}

                            <!-- Actions -->
                            {#if info.actions.length > 0}
                                <div
                                    class="flex flex-wrap items-center gap-1 ml-6"
                                >
                                    <span class="text-xs text-gray-400 mr-1"
                                        >Actions:</span
                                    >
                                    {#each info.actions as action}
                                        <span
                                            class="{actionColor(
                                                action,
                                            )} text-xs px-2 py-0.5 rounded-full font-medium"
                                            >{action}</span
                                        >
                                    {/each}
                                </div>
                            {/if}

                            <!-- Conditions -->
                            {#if isTruthy(info.conditions)}
                                <div
                                    class="flex flex-wrap items-center gap-1 ml-6"
                                >
                                    <span class="text-xs text-gray-400 mr-1"
                                        >Conditions:</span
                                    >
                                    {#each info.conditions as cond}
                                        <span
                                            class="{conditionColor(
                                                cond,
                                            )} text-xs px-2 py-0.5 rounded-full font-medium"
                                            >{cond}</span
                                        >
                                    {/each}
                                </div>
                            {/if}

                            <!-- Allowed fields values -->
                            {#if isTruthy(info.allowed_fields_values)}
                                <div class="ml-6">
                                    <span
                                        class="text-xs text-gray-400 block mb-0.5"
                                        >Allowed Fields Values:</span
                                    >
                                    <pre
                                        class="text-xs bg-green-50 border border-green-200 rounded p-2 overflow-auto max-h-32 text-green-900 font-mono">{pretty(
                                            info.allowed_fields_values,
                                        )}</pre>
                                </div>
                            {/if}

                            <!-- Filter fields values -->
                            {#if isTruthy(info.filter_fields_values)}
                                <div class="ml-6">
                                    <span
                                        class="text-xs text-gray-400 block mb-0.5"
                                        >Filter Fields Values:</span
                                    >
                                    <pre
                                        class="text-xs bg-sky-50 border border-sky-200 rounded p-2 overflow-auto max-h-32 text-sky-900 font-mono">{pretty(
                                            info.filter_fields_values,
                                        )}</pre>
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            </div>
        {/each}
    </div>
{/if}
