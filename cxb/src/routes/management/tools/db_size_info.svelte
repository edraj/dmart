<script lang="ts">
    import { Dmart } from "@edraj/tsdmart";
    import { onMount } from "svelte";
    import { goto } from "@roxi/routify";
    import { Spinner } from "flowbite-svelte";
    import { ArrowLeftOutline, DatabaseSolid } from "flowbite-svelte-icons";

    $goto;

    interface DbSizeEntry {
        table_name: string;
        pretty_size: string;
    }

    let isLoading = $state(true);
    let error: string | null = $state(null);
    let data: DbSizeEntry[] = $state([]);

    /** Convert a pretty_size string (e.g. "8047 MB", "80 kB", "16 bytes") to bytes for sorting. */
    function parseSizeToBytes(pretty: string): number {
        const units: Record<string, number> = {
            bytes: 1,
            byte: 1,
            kb: 1024,
            mb: 1024 ** 2,
            gb: 1024 ** 3,
            tb: 1024 ** 4,
        };
        const match = pretty.trim().match(/^([\d.]+)\s*(\S+)$/i);
        if (!match) return 0;
        const value = parseFloat(match[1]);
        const unit = match[2].toLowerCase();
        return value * (units[unit] ?? 0);
    }

    onMount(async () => {
        try {
            isLoading = true;
            const axiosInstance = Dmart.getAxiosInstance();
            const headers = Dmart.getHeaders();
            const response = await axiosInstance.get("db_size_info/", {
                headers,
            });
            if (response.data?.status === "success") {
                const raw: DbSizeEntry[] = response.data.data ?? [];
                data = raw
                    .slice()
                    .sort(
                        (a, b) =>
                            parseSizeToBytes(b.pretty_size) -
                            parseSizeToBytes(a.pretty_size),
                    );
            } else {
                error =
                    response.data?.error?.message ??
                    "Failed to load DB size info.";
            }
        } catch (err: any) {
            error =
                err?.message ??
                "An error occurred while fetching DB size info.";
        } finally {
            isLoading = false;
        }
    });
</script>

<div class="container mx-auto p-8">
    <button
        class="flex items-center gap-2 text-gray-600 hover:text-primary-600 mb-6 transition-colors"
        onclick={() => $goto("/management/tools")}
    >
        <ArrowLeftOutline size="sm" />
        <span>Back to Tools</span>
    </button>

    <div class="flex items-center gap-3 mb-8">
        <div class="p-3 bg-primary-100 rounded-full">
            <DatabaseSolid class="w-8 h-8 text-primary-600" />
        </div>
        <div>
            <h1 class="text-2xl font-bold">Database Size Info</h1>
            <p class="text-gray-500">
                View the size of each database table in the connected Dmart
                instance.
            </p>
        </div>
    </div>

    {#if error}
        <div
            class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50"
            role="alert"
        >
            <span class="font-medium">Error!</span>
            {error}
        </div>
    {/if}

    {#if isLoading}
        <div class="flex justify-center items-center h-64">
            <Spinner size="12" />
        </div>
    {:else if data.length === 0 && !error}
        <p class="text-gray-500 text-center mt-16">No data available.</p>
    {:else}
        <div
            class="overflow-x-auto rounded-lg border border-gray-200 shadow-sm"
        >
            <table class="w-full text-sm text-left text-gray-700">
                <thead
                    class="text-xs text-gray-700 uppercase bg-gray-50 border-b border-gray-200"
                >
                    <tr>
                        <th scope="col" class="px-6 py-4 font-semibold">#</th>
                        <th scope="col" class="px-6 py-4 font-semibold"
                            >Table Name</th
                        >
                        <th
                            scope="col"
                            class="px-6 py-4 font-semibold text-right">Size</th
                        >
                    </tr>
                </thead>
                <tbody>
                    {#each data as row, index}
                        <tr
                            class="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                        >
                            <td class="px-6 py-3 text-gray-400">{index + 1}</td>
                            <td class="px-6 py-3 font-medium"
                                >{row.table_name}</td
                            >
                            <td class="px-6 py-3 text-right">
                                <span
                                    class="inline-block bg-blue-50 text-blue-700 text-xs font-semibold px-3 py-1 rounded-full"
                                >
                                    {row.pretty_size}
                                </span>
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
        <p class="text-xs text-gray-400 mt-3">Total tables: {data.length}</p>
    {/if}
</div>
