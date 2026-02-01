<script lang="ts">
    import {Button, Label, Modal, Select, Spinner} from "flowbite-svelte";
    import {Dmart, RequestType, ResourceType} from "@edraj/tsdmart";
    import {Level, showToast} from "@/utils/toast";
    import {currentListView} from "@/stores/global";
    import {bulkBucket} from "@/stores/management/bulk_bucket";
    import {spaces} from "@/stores/management/spaces";
    import {getChildren, getChildrenAndSubChildren} from "@/lib/dmart_services";

    let {
        space_name,
        subpath,
        isOpen=$bindable(false),
        actionType = "move" // "move" or "copy"
    }:{
        space_name:string,
        subpath:string,
        isOpen:boolean,
        actionType: string
    } = $props();

    let selectedSpace = $state("");
    let selectedSubpath = $state("/");
    let isActionLoading = $state(false);
    let subpathOptions = $state([{name: "/", value: "/"}]);

    $effect(() => {
        if (isOpen) {
            selectedSpace = space_name;
            selectedSubpath = "/";
            fetchSubpaths(selectedSpace);
        }
    });

    async function fetchSubpaths(space) {
        if (!space) return;
        try {
            const response = await getChildren(space, "/", 100);
            let options = [{name: "/", value: "/"}];

            const subpaths = [];
            await getChildrenAndSubChildren(subpaths, space, "", response);
            subpaths.sort();

            subpaths.forEach(path => {
                options.push({
                    name: path,
                    value: path
                });
            });

            subpathOptions = options;
        } catch (e) {
            console.error("Failed to fetch subpaths", e);
            subpathOptions = [{name: "/", value: "/"}];
        }
    }

    function handleSpaceChange() {
        selectedSubpath = "/";
        fetchSubpaths(selectedSpace);
    }

    async function handleBulkAction() {
        if (!$bulkBucket.length) return;

        isActionLoading = true;
        try {
            const records = [];
            const isMove = actionType === "move";

            $bulkBucket.forEach(b => {
                if (isMove) {
                    const srcSubpath = subpath || "/";

                    const moveAttrb = {
                        src_space_name: space_name,
                        src_subpath: srcSubpath,
                        src_shortname: b.shortname,

                        dest_space_name: selectedSpace,
                        dest_subpath: selectedSubpath,
                        dest_shortname: b.shortname
                    };

                    records.push({
                        resource_type: b.resource_type,
                        shortname: b.shortname,
                        subpath: srcSubpath,
                        attributes: moveAttrb,
                    });
                } else {
                    // For copy, we use create request type to create a new item
                    // We copy attributes but NOT the UUID (a new one will be assigned)
                    const attrs = { ...b.attributes };
                    if ('uuid' in attrs) delete attrs.uuid;

                    records.push({
                        resource_type: b.resource_type,
                        shortname: b.shortname,
                        subpath: selectedSubpath,
                        attributes: attrs,
                    });
                }
            });

            const requestType = isMove ? RequestType.move : RequestType.create;
            const targetSpace = isMove ? space_name : selectedSpace;

            const response = await Dmart.request({
                space_name: targetSpace,
                request_type: requestType,
                records: records,
            });

            if (response?.status === "success") {
                showToast(Level.info, `Entries ${isMove ? "moved" : "copied"} successfully`);
                await $currentListView.fetchPageRecords();
                bulkBucket.set([]);
                isOpen = false;
            } else {
                showToast(Level.warn, `Failed to ${actionType} entries`);
            }
        } catch (e) {
            showToast(Level.warn, `Error during bulk ${actionType}`);
            console.error(e);
        } finally {
            isActionLoading = false;
        }
    }

    let spaceOptions = $derived($spaces ? $spaces.map(s => ({name: s.shortname, value: s.shortname})) : []);

</script>

<Modal bind:open={isOpen} size="md" title={`Bulk ${actionType === "move" ? "Move" : "Copy"}`}>
    <div class="space-y-4">
        <Label>
            Destination Space
            <Select class="mt-2" items={spaceOptions} bind:value={selectedSpace} onchange={handleSpaceChange} />
        </Label>

        <Label>
            Destination Subpath (All Folders)
            <Select class="mt-2" items={subpathOptions} bind:value={selectedSubpath} />
        </Label>
    </div>

    {#snippet footer()}
        <div class="flex justify-between w-full">
            <Button color="alternative" onclick={() => isOpen = false}>Cancel</Button>
            <Button class="bg-primary" onclick={handleBulkAction} disabled={isActionLoading}>
                {#if isActionLoading}
                    <Spinner size="sm" class="mr-2" />
                    {actionType === "move" ? "Moving..." : "Copying..."}
                {:else}
                    {actionType === "move" ? "Move" : "Copy"}
                {/if}
            </Button>
        </div>
    {/snippet}
</Modal>
