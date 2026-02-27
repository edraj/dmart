<script>
    import { Card } from "flowbite-svelte";
    import {
        CalendarMonthOutline,
        InfoCircleOutline,
        SearchOutline,
        FileImportOutline,
        FileExportOutline,
        PaletteOutline,
        ChartPieOutline,
    } from "flowbite-svelte-icons";
    import { goto } from "@roxi/routify";
    $goto;
    let gitHash = import.meta.env.VITE_GIT_HASH ?? "N/A";
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
    </div>
</div>
