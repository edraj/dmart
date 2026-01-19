<script>
    import {spaces} from "@/stores/management/spaces";
    import {Button, Card, Dropdown, DropdownItem, Modal, Spinner} from "flowbite-svelte";
    import {DotsHorizontalOutline, EyeSolid, PenSolid, PlusOutline, TrashBinSolid} from "flowbite-svelte-icons";
    import {JSONEditor, Mode} from "svelte-jsoneditor";
    import {jsonEditorContentParser} from "@/utils/jsonEditor";
    import {getSpaces} from "@/lib/dmart_services";
    import {Dmart, RequestType, ResourceType} from "@edraj/tsdmart";
    import {Level, showToast} from "@/utils/toast";
    import Prism from "@/components/Prism.svelte";
    import {goto} from "@roxi/routify";
    import MetaForm from "@/components/management/forms/MetaForm.svelte";
    import {removeEmpty} from "@/utils/compare.js";

    $goto

    let viewMetaModal = $state(false);
    let editModal = $state(false);
    let deleteModal = $state(false);
    let addSpaceModal = $state(false);
    let selectedSpace = $state(null);
    let modelError = $state(null);

    let spaceFormData = $state({
        shortname: "",
        is_active: true,
        slug: "",
        displayname: {
            en: "",
            ar: "",
            ku: ""
        },
        description: {
            en: "",
            ar: "",
            ku: ""
        }
    });
    let validateSpaceForm = $state(() => true);

    let isActionLoading = $state(false);

    let jeContent = $state({ json: undefined });

    function showAddSpaceModal() {
        modelError = null;
        spaceFormData = {
            shortname: "",
            is_active: true,
            slug: "",
            displayname: {
                en: "",
                ar: "",
                ku: ""
            },
            description: {
                en: "",
                ar: "",
                ku: ""
            }
        };
        addSpaceModal = true;
    }

    async function createSpace() {
        if (!validateSpaceForm()) {
            return;
        }

        if (spaceFormData.shortname.trim()) {
            try {
                isActionLoading = true;
                modelError = null;
                const attributes = {
                    is_active: spaceFormData.is_active,
                    slug: spaceFormData.slug,
                    displayname: spaceFormData.displayname,
                    description: spaceFormData.description
                };
                await Dmart.request({
                    space_name: spaceFormData.shortname.trim(),
                    request_type: RequestType.create,
                    records: [
                        {
                            resource_type: ResourceType.space,
                            shortname: spaceFormData.shortname.trim(),
                            subpath: '/',
                            attributes: removeEmpty(attributes)
                        }
                    ]
                });
                showToast(Level.info, `Space "${spaceFormData.shortname.trim()}" created successfully!`);
                await getSpaces();
                addSpaceModal = false;
            } catch (error) {
                modelError = error.response.data;
            } finally {
                isActionLoading = false;
            }
        }
    }

    function viewMeta(space) {
        modelError = null;
        selectedSpace = structuredClone(space);
        jeContent = { json: selectedSpace };
        viewMetaModal = true;
    }

    function editSpace(space) {
        modelError = null;
        selectedSpace = structuredClone(space);
        jeContent = { json: selectedSpace };
        editModal = true;
    }

    async function saveChanges() {
        if (selectedSpace) {
            const record = jsonEditorContentParser(
                $state.snapshot(jeContent)
            );
            delete record.uuid;
            try {
                isActionLoading = true;
                modelError = null;
                await Dmart.request({
                    space_name: selectedSpace.shortname,
                    request_type: RequestType.update,
                    records: [
                        {
                            resource_type: ResourceType.space,
                            shortname: selectedSpace.shortname,
                            subpath: '/',
                            attributes: record.attributes
                        }
                    ]
                })
                editModal = false;
                showToast(Level.info, `Space "${selectedSpace.shortname}" updated successfully!`);
                await getSpaces();
            } catch (error) {
                modelError = error;
            } finally {
                isActionLoading = false;
            }
        }
    }

    function confirmDelete(space) {
        modelError = null;
        selectedSpace = space;
        deleteModal = true;
    }

    async function deleteSpace() {
        if (selectedSpace) {

            try {
                isActionLoading = true;
                modelError = null;
                await Dmart.request({
                    space_name: selectedSpace.shortname,
                    request_type: RequestType.delete,
                    records: [{
                        resource_type: ResourceType.space,
                        shortname: selectedSpace.shortname,
                        subpath: '/',
                        attributes: {}
                    }]
                })
                showToast(Level.info, `Space "${selectedSpace.shortname}" has been deleted successfully!`);
                deleteModal = false;
                selectedSpace = null;
                await getSpaces();
            } catch (error) {
                modelError = error;
            } finally {
                isActionLoading = false;
            }
        }
    }

    async function handleSelectedSpace(spaceShortname) {
        $goto(`/management/content/[space_name]`, {
            space_name: spaceShortname
        });
    }
</script>

<div class="container mx-auto px-12 py-6">
    <div class="flex justify-between items-center mb-1 px-1">
        <h1 class="text-2xl font-bold mb-6">All Spaces</h1>
        <Button size="md" class="bg-primary" style="cursor: pointer" onclick={showAddSpaceModal}>
            <PlusOutline class="me-2 h-5 w-5" />Add new space
        </Button>
    </div>
    <hr class="mb-6 border-gray-300" />
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 gap-4 w-full place-items-center">
        {#each ($spaces ?? []).filter(space => space?.attributes?.hide_space !== true) as space}
            <Card class="relative w-full">
                <div class="absolute top-2 left-2">
                    <Button class="!p-1" color="light">
                        <DotsHorizontalOutline />
                        <Dropdown simple>
                            <DropdownItem class="w-full" onclick={() => viewMeta(space)}>
                                <div class="flex items-center gap-2">
                                    <EyeSolid size="sm" /> View Meta
                                </div>
                            </DropdownItem>
                            <DropdownItem class="w-full" onclick={() => editSpace(space)}>
                                <div class="flex items-center gap-2">
                                    <PenSolid size="sm" /> Edit
                                </div>
                            </DropdownItem>
                            <DropdownItem class="w-full" onclick={() => confirmDelete(space)}>
                                <div class="flex items-center gap-2 text-red-600">
                                    <TrashBinSolid size="sm" /> Delete
                                </div>
                            </DropdownItem>
                        </Dropdown>
                    </Button>
                </div>

                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <div class="flex flex-col items-center text-center p-4"
                     style="cursor: pointer"
                     onclick={() => handleSelectedSpace(space.shortname)}>
                    <span class="inline-block px-3 py-1 mb-3 border border-gray-300 rounded-md text-sm font-medium">
                        {space.shortname}
                    </span>

                    <h3 class="font-semibold text-lg">{space.attributes?.displayname?.en || space.shortname}</h3>

                    <p class="text-gray-600 mt-2 mb-4 line-clamp-3">
                        {space?.description?.en || ""}
                    </p>

                    <div class="text-xs text-gray-500 mt-auto">
                        Updated: {new Date(space?.attributes.updated_at).toLocaleDateString()}
                    </div>
                </div>
            </Card>
        {/each}
    </div>
</div>

<Modal bind:open={addSpaceModal} size="xl" title="Add New Space">
    <div class="space-y-4">
        <MetaForm bind:formData={spaceFormData} bind:validateFn={validateSpaceForm} isCreate={true}/>

        {#if modelError}
            <div class="mt-4">
                <p class="text-red-600 font-medium mb-2">Error:</p>
                <div class="max-h-60 overflow-auto">
                    <Prism code={modelError} />
                </div>
            </div>
        {/if}
    </div>

    <div class="flex justify-between w-full mt-4">
        <Button color="alternative" onclick={() => addSpaceModal = false}>Cancel</Button>
        <Button class="bg-primary" onclick={createSpace}>
            {#if isActionLoading}
                <Spinner class="me-3" size="4" color="blue" />
                Creating ...
            {:else}
                Create
            {/if}
        </Button>
    </div>
</Modal>

<Modal bind:open={viewMetaModal} size="xl" title="Space Metadata" autoclose>
    <div>
        {#if selectedSpace}
            <JSONEditor content={jeContent} readOnly={true} />
        {/if}
    </div>
</Modal>

<Modal bind:open={editModal} size="xl" title="Edit Space">
    <div>
        {#if selectedSpace}
            <JSONEditor bind:content={jeContent} readOnly={false} mode={Mode.text} />
        {/if}

        {#if modelError}
            <div class="mt-4">
                <p class="text-red-600 font-medium mb-2">Error:</p>
                <div class="max-h-60 overflow-auto">
                    <Prism code={modelError} />
                </div>
            </div>
        {/if}
    </div>
    <div class="flex justify-between w-full">
        <Button color="alternative" onclick={() => editModal = false}>Cancel</Button>
        <Button class="bg-primary" onclick={saveChanges}>
            {#if isActionLoading}
                <Spinner class="me-3" size="4" color="blue" />
                Saving Changes ...
            {:else}
                Save Changes
            {/if}
        </Button>
    </div>
</Modal>

<Modal bind:open={deleteModal} size="md" title="Confirm Deletion">
    {#if selectedSpace}
        <p class="text-center mb-6">
            Are you sure you want to delete the space <span class="font-bold">{selectedSpace.shortname}</span>?<br>
            This action cannot be undone.
        </p>
    {/if}

    {#if modelError}
        <div class="mt-4">
            <p class="text-red-600 font-medium mb-2">Error:</p>
            <div class="max-h-60 overflow-auto">
                <Prism code={modelError} />
            </div>
        </div>
    {/if}

    <div class="flex justify-between w-full">
        <Button color="alternative" onclick={() => deleteModal = false}>Cancel</Button>
        <Button color="red" onclick={deleteSpace}>
            {#if isActionLoading}
                <Spinner class="me-3" size="4" color="blue" />
                Deleting ...
            {:else}
                Delete
            {/if}
        </Button>
    </div>
</Modal>
