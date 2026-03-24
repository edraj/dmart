<script lang="ts">
    import { Card } from "flowbite-svelte";
    import {
        CalendarMonthOutline,
        InfoCircleOutline,
        SearchOutline,
        FileImportOutline,
        FileExportOutline,
        PaletteOutline,
        ChartPieOutline,
        DatabaseSolid,
        ChartLineUpOutline,
        TrashBinOutline,
    } from "flowbite-svelte-icons";
    import { goto } from "@roxi/routify";
    import { Dmart } from "@edraj/tsdmart";
    import { onMount } from "svelte";

    $goto;
    let gitHash = import.meta.env.VITE_GIT_HASH ?? "N/A";

    let plugins: string[] = $state([]);

    onMount(async () => {
        const manifest = await Dmart.getManifest();
        if (manifest?.status === "success") {
            plugins = manifest.attributes?.plugins ?? [];
        }
    });
</script>

<div class="container mx-auto p-8">
    <p class="text-2xl mb-5">HASH: {gitHash}</p>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/info")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <InfoCircleOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">INFORMATION</h3>
                <p class="text-gray-600">
                    Get information about connected instance of Dmart.
                </p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/events")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <CalendarMonthOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Events</h3>
                <p class="text-gray-600">Check all Dmart instance events.</p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/query")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <SearchOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Query</h3>
                <p class="text-gray-600">
                    Perform queries against connected dmart instance.
                </p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/import")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <FileImportOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Import</h3>
                <p class="text-gray-600">Import entries based on zip file.</p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/export")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <FileExportOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Export</h3>
                <p class="text-gray-600">Export entries as zip file.</p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/theme")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <PaletteOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Theme</h3>
                <p class="text-gray-600">
                    Customize the navigation bar colors.
                </p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/statistics")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-primary-100 rounded-full mb-4">
                    <ChartPieOutline class="w-12 h-12 text-primary-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Statistics</h3>
                <p class="text-gray-600">
                    View application usage and space statistics.
                </p>
            </div>
        </Card>

        <Card
            class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
            onclick={() => $goto("/management/tools/trash")}
        >
            <div class="flex flex-col items-center text-center">
                <div class="p-3 bg-red-100 rounded-full mb-4">
                    <TrashBinOutline class="w-12 h-12 text-red-600" />
                </div>
                <h3 class="text-xl font-bold mb-2">Trash</h3>
                <p class="text-gray-600">
                    View and manage your deleted items.
                </p>
            </div>
        </Card>

        {#if plugins.includes("db_size_info")}
            <Card
                class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
                onclick={() => $goto("/management/tools/db_size_info")}
            >
                <div class="flex flex-col items-center text-center">
                    <div class="p-3 bg-primary-100 rounded-full mb-4">
                        <DatabaseSolid class="w-12 h-12 text-primary-600" />
                    </div>
                    <h3 class="text-xl font-bold mb-2">DB Size Info</h3>
                    <p class="text-gray-600">
                        View the size of each database table.
                    </p>
                </div>
            </Card>
        {/if}

        {#if plugins.includes("db_entries_count_history")}
            <Card
                class="p-4 hover:shadow-lg transition-shadow cursor-pointer"
                onclick={() =>
                    $goto("/management/tools/db_entries_count_history")}
            >
                <div class="flex flex-col items-center text-center">
                    <div class="p-3 bg-primary-100 rounded-full mb-4">
                        <ChartLineUpOutline
                            class="w-12 h-12 text-primary-600"
                        />
                    </div>
                    <h3 class="text-xl font-bold mb-2">
                        Entries Count History
                    </h3>
                    <p class="text-gray-600">
                        Track the growth of entries across spaces over time.
                    </p>
                </div>
            </Card>
        {/if}
    </div>
</div>
