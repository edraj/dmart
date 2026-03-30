<script lang="ts">
    import { onMount } from "svelte";
    import { Card, Label, Checkbox, Input, Select, Badge } from "flowbite-svelte";
    import { Dmart, QueryType, ResourceType } from "@edraj/tsdmart";
    import { CloseCircleSolid } from "flowbite-svelte-icons";

    let {
        formData = $bindable(),
        spaceName
    } : {
        formData: any,
        spaceName: string
    } = $props();

    let plugins = $state([]);
    let availableFolders = $state([]);

    formData = {
        ...formData,
        hide_folders: formData.hide_folders || [],
        hide_space: formData.hide_space ?? false,
        active_plugins: formData.active_plugins || [],
        ordinal: formData.ordinal ?? 0,
    };

    onMount(async () => {
        // Fetch plugins
        try {
            const manifest = await Dmart.getManifest();
            if (manifest?.status === "success") {
                plugins = manifest.attributes?.plugins ?? [];
            }
        } catch (e) {
            console.error("Failed to fetch manifest", e);
        }

        // Fetch top folders of the managed space
        try {
            const foldersFull = await Dmart.query({
                type: QueryType.search,
                space_name: spaceName,
                subpath: "/",
                exact_subpath: true,
                filter_types: [ResourceType.folder],
                limit: 100,
                search: ""
            });
            availableFolders = (foldersFull.records || []).map(r => r.shortname);
        } catch (e) {
            console.error("Failed to fetch folders", e);
        }
    });

    function addItem(listName: string, value: string) {
        if (value && !formData[listName].includes(value)) {
            formData[listName] = [...formData[listName], value];
        }
    }

    function removeItem(listName: string, value: string) {
        formData[listName] = formData[listName].filter((v: string) => v !== value);
    }
</script>

<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    <div class="space-y-6">
        <h2 class="text-2xl font-bold mb-4">Space Configuration</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <Label for="ordinal" class="mb-2">Ordinal</Label>
                <Input id="ordinal" type="number" bind:value={formData.ordinal} />
                <p class="text-xs text-gray-500 mt-1">Numerical order for space listing</p>
            </div>

            <div class="flex flex-col justify-center">
                <div class="flex items-center gap-2">
                    <Checkbox id="hide_space" bind:checked={formData.hide_space} />
                    <Label for="hide_space" class="mb-0 font-normal">Hide Space</Label>
                </div>
                <p class="text-xs text-gray-500 mt-1">If checked, this space will be hidden from the sidebar</p>
            </div>
        </div>

        <div class="border p-4 rounded-lg bg-gray-50 dark:bg-gray-800">
            <Label for="hide_folders" class="mb-2 font-semibold">Hide Folders</Label>
            <div class="flex flex-wrap gap-2 mb-3">
                {#each formData.hide_folders as folder}
                    <Badge color="blue" class="flex items-center gap-1">
                        {folder}
                        <button type="button" onclick={() => removeItem('hide_folders', folder)} class="ml-1">
                            <CloseCircleSolid size="xs" class="hover:text-red-500 cursor-pointer" />
                        </button>
                    </Badge>
                {/each}
                {#if formData.hide_folders.length === 0}
                    <p class="text-sm text-gray-400 italic">No folders hidden</p>
                {/if}
            </div>
            <Select
                id="hide_folders_select"
                items={availableFolders.filter(f => !formData.hide_folders.includes(f)).map(f => ({ name: f, value: f }))}
                placeholder="Select folder to hide..."
                onchange={(e) => {
                    const target = e.target as HTMLSelectElement;
                    addItem('hide_folders', target.value);
                    target.value = "";
                }}
            />
            <p class="text-xs text-gray-500 mt-1">Choose top-level folders to hide in this space</p>
        </div>

        <div class="border p-4 rounded-lg bg-gray-50 dark:bg-gray-800">
            <Label for="active_plugins" class="mb-2 font-semibold">Active Plugins</Label>
            <div class="flex flex-wrap gap-2 mb-3">
                {#each formData.active_plugins as plugin}
                    <Badge color="green" class="flex items-center gap-1">
                        {plugin}
                        <button type="button" onclick={() => removeItem('active_plugins', plugin)} class="ml-1">
                            <CloseCircleSolid size="xs" class="hover:text-red-500 cursor-pointer" />
                        </button>
                    </Badge>
                {/each}
                {#if formData.active_plugins.length === 0}
                    <p class="text-sm text-gray-400 italic">No active plugins</p>
                {/if}
            </div>
            <Select
                id="active_plugins_select"
                items={plugins.filter(p => !formData.active_plugins.includes(p)).map(p => ({ name: p, value: p }))}
                placeholder="Select plugin to activate..."
                onchange={(e) => {
                    const target = e.target as HTMLSelectElement;
                    addItem('active_plugins', target.value);
                    target.value = "";
                }}
            />
            <p class="text-xs text-gray-500 mt-1">Choose plugins enabled for this space</p>
        </div>
    </div>
</Card>
