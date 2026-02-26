<script lang="ts">
    import { onMount, type ComponentProps } from "svelte";
    import { Card, Spinner } from "flowbite-svelte";
    import {
        UsersSolid,
        LockSolid,
        ShieldCheckSolid,
        DatabaseSolid,
        FolderSolid,
        FileCodeSolid,
        ArrowLeftOutline,
    } from "flowbite-svelte-icons";
    import { Dmart, QueryType } from "@edraj/tsdmart";
    import { getSpaces } from "@/lib/dmart_services";
    import { goto } from "@roxi/routify";

    $goto;

    let isLoading = $state(true);
    let error: string | null = $state(null);

    let mgmtStats = $state({
        users: 0,
        roles: 0,
        permissions: 0,
        totalSpaces: 0,
        totalRecords: 0,
    });

    interface SpaceStat {
        shortname: string;
        total: number;
        entriesOrFolders: number;
        schemas: number;
        folders: number;
    }

    let spaceStats: SpaceStat[] = $state([]);

    async function fetchCount(space: string, resource_type: string, by_subpath = false): Promise<number> {
        try {
            const resp = await Dmart.query({
                type: QueryType.counters,
                retrieve_total: true,
                space_name: space,
                exact_subpath: false,
                subpath: by_subpath ? resource_type : '/',
                search: by_subpath ? '' : `@resource_type:${resource_type}`,
            } as any);
            return resp.attributes.total || 0;
        } catch (e) {
            console.error(`Failed to fetch count for ${space}/${resource_type}`, e);
            return 0;
        }
    }

    onMount(async () => {
        try {
            isLoading = true;

            // Fetch management/system stats
            const [users, roles, permissions] = await Promise.all([
                fetchCount("management", "users", true),
                fetchCount("management", "roles", true),
                fetchCount("management", "permissions", true),
            ]);

            mgmtStats.users = users;
            mgmtStats.roles = roles;
            mgmtStats.permissions = permissions;

            // Fetch space level stats
            const spacesObj = await getSpaces();
            let totalOverallRecords = 0;
            const sStats: SpaceStat[] = [];

            // Loop sequentially or wait for all map fetches depending on network stress
            const spacePromises = spacesObj.records.map(
                async (spaceData: any) => {
                    const sn = spaceData.shortname;

                    const [total, schemas, folders] = await Promise.all([
                        fetchCount(sn, "*"),
                        fetchCount(sn, "schema"),
                        fetchCount(sn, "folder"),
                    ]);

                    // Subtract the schemas/folders from total to roughly get "entries + folders"
                    // Assuming `/` QueryType.counters with retrieve_total=true will fetch overall or root entries
                    // Actually, `/` usually implies everything or root. Let's assume total is everything.
                    const entriesOrFolders = Math.max(
                        0,
                        total - schemas - folders,
                    );

                    totalOverallRecords += total;

                    return {
                        shortname: sn,
                        total,
                        entriesOrFolders,
                        schemas,
                        folders,
                    };
                },
            );

            const resolvedSpaceStats = await Promise.all(spacePromises);

            spaceStats = resolvedSpaceStats;
            mgmtStats.totalSpaces = resolvedSpaceStats.length;
            mgmtStats.totalRecords = totalOverallRecords;
        } catch (err: any) {
            error = "Failed to load statistics. " + err.message;
        } finally {
            isLoading = false;
        }
    });
</script>

<div class="container mx-auto p-8 relative">
    <div class="flex items-center mb-6">
        <button
            class="mr-4 p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            onclick={() => $goto("/management/tools")}
        >
            <ArrowLeftOutline class="w-6 h-6" />
        </button>
        <h1 class="text-3xl font-bold">Statistics</h1>
    </div>

    {#if error}
        <div
            class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400"
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
    {:else}
        <!-- Top Level Stats -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <Card
                class="p-4 flex flex-col items-center justify-center text-center"
            >
                <UsersSolid class="w-10 h-10 text-blue-500 mb-2" />
                <h3 class="text-4xl font-bold mb-1">{mgmtStats.users}</h3>
                <p
                    class="text-gray-500 uppercase text-sm font-semibold tracking-wide"
                >
                    Total Users
                </p>
            </Card>

            <Card
                class="p-4 flex flex-col items-center justify-center text-center"
            >
                <ShieldCheckSolid class="w-10 h-10 text-green-500 mb-2" />
                <h3 class="text-4xl font-bold mb-1">{mgmtStats.roles}</h3>
                <p
                    class="text-gray-500 uppercase text-sm font-semibold tracking-wide"
                >
                    Total Roles
                </p>
            </Card>

            <Card
                class="p-4 flex flex-col items-center justify-center text-center"
            >
                <LockSolid class="w-10 h-10 text-red-500 mb-2" />
                <h3 class="text-4xl font-bold mb-1">{mgmtStats.permissions}</h3>
                <p
                    class="text-gray-500 uppercase text-sm font-semibold tracking-wide"
                >
                    Total Permissions
                </p>
            </Card>

            <Card
                class="p-4 flex flex-col items-center justify-center text-center bg-gray-50 dark:bg-gray-800"
            >
                <DatabaseSolid class="w-10 h-10 text-purple-500 mb-2" />
                <h3
                    class="text-4xl font-bold mb-1 text-purple-700 dark:text-purple-400"
                >
                    {mgmtStats.totalRecords}
                </h3>
                <p
                    class="text-gray-500 uppercase text-sm font-semibold tracking-wide"
                >
                    Records in {mgmtStats.totalSpaces} spaces
                </p>
            </Card>
        </div>

        <!-- Space Breakdown -->
        <h2 class="text-2xl font-bold mb-4 mt-8">Space Statistics</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {#each spaceStats as stat}
                <Card
                    class="w-full max-w-none hover:shadow-lg transition-shadow"
                >
                    <div
                        class="flex items-center justify-between border-b pb-4 mb-4"
                    >
                        <div class="flex items-center gap-3">
                            <div
                                class="p-2 bg-primary-100 dark:bg-primary-900 rounded-lg"
                            >
                                <FolderSolid
                                    class="w-6 h-6 text-primary-600 dark:text-primary-400"
                                />
                            </div>
                            <h3
                                class="text-xl font-bold truncate max-w-[200px]"
                                title={stat.shortname}
                            >
                                {stat.shortname}
                            </h3>
                        </div>
                        <span
                            class="bg-gray-100 text-gray-800 text-sm font-medium px-3 py-1 rounded-full dark:bg-gray-700 dark:text-gray-300"
                        >
                            Total: {stat.total}
                        </span>
                    </div>

                    <div class="grid grid-cols-3 gap-2 text-center mt-2">
                        <div class="p-2 rounded bg-gray-50 dark:bg-gray-800">
                            <FileCodeSolid
                                class="w-5 h-5 mx-auto text-yellow-500 mb-1"
                            />
                            <div class="text-xl font-bold">{stat.schemas}</div>
                            <div class="text-xs text-gray-500 uppercase">
                                Schemas
                            </div>
                        </div>
                        <div class="p-2 rounded bg-gray-50 dark:bg-gray-800">
                            <FolderSolid
                                class="w-5 h-5 mx-auto text-blue-500 mb-1"
                            />
                            <div class="text-xl font-bold">
                                {stat.folders}
                            </div>
                            <div class="text-xs text-gray-500 uppercase">
                                Folders
                            </div>
                        </div>
                        <div class="p-2 rounded bg-gray-50 dark:bg-gray-800">
                            <FolderSolid
                                class="w-5 h-5 mx-auto text-teal-500 mb-1"
                            />
                            <div class="text-xl font-bold">
                                {stat.entriesOrFolders}
                            </div>
                            <div class="text-xs text-gray-500 uppercase">
                                Entries
                            </div>
                        </div>
                    </div>
                </Card>
            {/each}
        </div>
    {/if}
</div>
