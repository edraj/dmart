<script lang="ts">
    import {
        ClockArrowOutline,
        CloseOutline,
        DownloadOutline,
        FileCirclePlusOutline,
        FileCopyOutline,
        FileExportOutline,
        SearchOutline,
        TrashBinOutline,
        UploadOutline
    } from "flowbite-svelte-icons";
    import {Button, ButtonGroup, Input, InputAddon, Modal} from "flowbite-svelte";
    import ModalCreateEntry from "@/components/management/Modals/ModalCreateEntry.svelte";
    import ModalCSVUpload from "@/components/management/Modals/ModalCSVUpload.svelte";
    import ModalCSVDownload from "@/components/management/Modals/ModalCSVDownload.svelte";
    import ModalBulkMoveCopy from "@/components/management/Modals/ModalBulkMoveCopy.svelte";
    import {onMount} from "svelte";
    import {checkAccess} from "@/utils/checkAccess";
    import {currentEntry, currentListView, subpathInManagementNoAction} from "@/stores/global";
    import {bulkBucket} from "@/stores/management/bulk_bucket";
    import {Dmart, RequestType, ResourceType} from "@edraj/tsdmart";
    import {Level, showToast} from "@/utils/toast";
    import {searchListView} from "@/stores/management/triggers";
    import {user} from "@/stores/user";
    import {goto, params} from "@roxi/routify";

    $goto
    let {space_name,subpath}:{space_name:string,subpath:string} = $props();

    let canCreate = $state(false);
    let canUploadCSV = $state(false);
    let canDownloadCSV = $state(false);
    let canDelete = $state(false);
    let isCSVDownloadModalOpen = $state(false);

    const isEntryTrash = space_name === "personal" && subpath.startsWith(`people/${$user.shortname}/trash`)

    onMount(() => {
        if($currentEntry.entry?.payload?.body?.allow_csv){
            canDownloadCSV = true
        }
        if($currentEntry.entry?.payload?.body?.allow_upload_csv){
            canUploadCSV = true
        }

        if(space_name === "management" && subpath === "/") {
            canCreate = false;
            canDelete = false;
            canUploadCSV = false;
            return;
        } else if (space_name === "management" && subpath === "health_check"){
            canCreate = false;
            canUploadCSV = false;
            return;
        }
        if (space_name === "management"){
            if(subpathInManagementNoAction.includes(subpath)) {
                canCreate = checkAccess("create", space_name, subpath, subpath.slice(0,-1));
            } else {
                canCreate = checkAccess("create", space_name, subpath, "content");
            }
        } else {
            canCreate = checkAccess("create", space_name, subpath, "content") || checkAccess("create", space_name, subpath, "folder");
        }

    });

    let isOpen = $state(false);


    let isActionLoading = $state(false);
    let openDeleteModal = $state(false);
    function deleteCurrentEntry() {
        openDeleteModal = true;
    }
    async function handleBulkDelete() {
        if ($bulkBucket.length) {
            try {
                isActionLoading = true;
                const records = []
                $bulkBucket.map(b => {
                    records.push({
                        resource_type: b.resource_type,
                        shortname: b.shortname,
                        subpath: subpath || "/",
                        attributes: {},
                    });
                });

                const request_body = {
                    space_name,
                    request_type: RequestType.delete,
                    records: records,
                };
                const response = await Dmart.request(request_body);

                if (response?.status === "success") {
                    showToast(Level.info);
                } else {
                    showToast(Level.warn);
                }
                await $currentListView.fetchPageRecords();
                bulkBucket.set([]);
            } catch (e) {
                showToast(Level.warn, "Failed to delete entries. Please try again later.");
            } finally {
                isActionLoading = false;
                openDeleteModal = false;
            }
        }
    }

    let searchInput = $state($searchListView);
    async function handleSearch(e){
        searchListView.set(searchInput);
        if(searchInput){
            $goto('$leaf', {...$params, 'search': searchInput});
        } else {
            delete $params.search;
            $goto('$leaf', $params);
        }
    }


    let isCSVUploadModalOpen = $state(false);
    function handleCSVUploadModal() {
        isCSVUploadModalOpen = true;
    }

    async function restoreEntries() {
        isActionLoading = true;

        try {
            const records = [];

            $bulkBucket.map(b => {
                const scr_subpaths: string[] = b.subpath.split('/');
                const remaining: string[] = scr_subpaths.slice(3);

                const distSpacename = remaining[0];
                const distSubpath = remaining.slice(1).join('/') ;

                const moveResourceType = b.resource_type
                    || (b.subpath && ResourceType.folder)
                    || ResourceType.space;

                const moveAttrb = {
                    src_space_name: 'personal',
                    src_subpath: b.subpath.replaceAll("-", "/"),
                    src_shortname: b.shortname,

                    dest_space_name: distSpacename,
                    dest_subpath: distSubpath.replaceAll("-", "/"),
                    dest_shortname: b.shortname
                };

                records.push({
                    resource_type: moveResourceType,
                    shortname: b.shortname,
                    subpath: b.subpath.replaceAll("-", "/"),
                    attributes: moveAttrb,
                });
            });

            await Dmart.request({
                space_name: 'personal',
                request_type: RequestType.move,
                records: records,
            });
            await $currentListView.fetchPageRecords();
            showToast(Level.info, `Entries restored successfully`);
        } catch (error) {
            showToast(Level.warn, `Failed to restore the entries!`);
        } finally {
            isActionLoading = false;
        }
    }

    let isBulkMoveCopyOpen = $state(false);
    let bulkActionType = $state("move");

    function openBulkMove() {
        bulkActionType = "move";
        isBulkMoveCopyOpen = true;
    }

    function openBulkCopy() {
        bulkActionType = "copy";
        isBulkMoveCopyOpen = true;
    }
</script>

<div class="flex flex-col md:flex-row justify-between items-center my-2 mx-3">
    <div class="w-1/2">
        <form on:submit|preventDefault={handleSearch}>
            <ButtonGroup class="w-full">
                <Input id="website-admin" placeholder="Search..." bind:value={searchInput} type="search"/>
                {#if searchInput.length > 0}
                    <InputAddon class="cursor-pointer" onclick={(e)=>{searchInput='';handleSearch(e)}}>
                        <CloseOutline class="h-4 w-4 text-gray-500 dark:text-gray-400" />
                    </InputAddon>
                {/if}
                <InputAddon class="cursor-pointer" onclick={handleSearch}>
                    <SearchOutline class="h-4 w-4 text-gray-500 dark:text-gray-400" />
                </InputAddon>
            </ButtonGroup>
        </form>
    </div>
    <div>
        {#if canCreate}
            <Button class="bg-primary cursor-pointer" size="xs" onclick={() => isOpen = true}>
                <FileCirclePlusOutline size="md"/> Create
            </Button>
        {/if}
        {#if canUploadCSV}
            <Button class="text-primary cursor-pointer hover:text-primary" size="xs" outline
                    onclick={handleCSVUploadModal}>
                <UploadOutline size="md"/> Upload
            </Button>
        {/if}
        {#if canDownloadCSV}
            <Button class="text-primary cursor-pointer hover:text-primary" size="xs" outline
                    onclick={() => isCSVDownloadModalOpen = true}>
                <DownloadOutline size="md"/> Download
            </Button>
        {/if}
        {#if canDelete}
            <Button class="text-red-600 cursor-pointer hover:text-red-600" size="xs" outline>
                <TrashBinOutline size="md"/> Delete
            </Button>
        {/if}
        {#if $bulkBucket.length}
            {#if isEntryTrash}
                <Button class="text-primary cursor-pointer hover:text-primary" size="xs" outline onclick={restoreEntries}>
                    <ClockArrowOutline size="md"/> Restore
                </Button>
            {:else}
                <Button class="text-primary cursor-pointer hover:text-primary" size="xs" outline onclick={openBulkMove}>
                    <FileExportOutline size="md"/> Bulk Move
                </Button>
                <Button class="text-primary cursor-pointer hover:text-primary" size="xs" outline onclick={openBulkCopy}>
                    <FileCopyOutline size="md"/> Bulk Copy
                </Button>
                <Button class="text-red-600 cursor-pointer hover:text-red-600" size="xs" outline onclick={deleteCurrentEntry}>
                    <TrashBinOutline size="md"/> Bulk delete
                </Button>
            {/if}
        {/if}
    </div>
</div>

{#if canCreate}
    <ModalCreateEntry {space_name} {subpath} bind:isOpen={isOpen} />
{/if}

{#if canUploadCSV}
    <ModalCSVUpload {space_name} {subpath} bind:isOpen={isCSVUploadModalOpen} />
{/if}

{#if canDownloadCSV}
    <ModalCSVDownload {space_name} {subpath} bind:isOpen={isCSVDownloadModalOpen}/>
{/if}

<ModalBulkMoveCopy {space_name} {subpath} bind:isOpen={isBulkMoveCopyOpen} actionType={bulkActionType} />

<Modal bind:open={openDeleteModal} size="md" title="Confirm Deletion">
    <p class="text-center mb-6">
        Are you sure you want to delete <span class="font-bold">{$bulkBucket.map(e => e.shortname).join(", ")}</span> {$bulkBucket.length === 1 ? "entry" : "entries"}?<br>
        This action cannot be undone.
    </p>

    <div class="flex justify-between w-full">
        <Button color="alternative" onclick={() => openDeleteModal = false}>Cancel</Button>
        <Button color="red" onclick={handleBulkDelete} disabled={isActionLoading}>{isActionLoading ? "Deleting..." : "Delete"}</Button>
    </div>
</Modal>