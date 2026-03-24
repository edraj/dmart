<script lang="ts">
    import { _ } from "svelte-i18n";
    import { Button, Card, Input, Label, Modal, Select } from "flowbite-svelte";
    import { Dmart, RequestType, ResourceType } from "@edraj/tsdmart";
    import { Level, showToast } from "@/utils/toast";
    import { JSONEditor, Mode } from "svelte-jsoneditor";
    import {
        getChildren,
        getChildrenAndSubChildren,
    } from "@/lib/dmart_services";
    import {
        PlusOutline,
        TrashBinSolid,
        PenSolid,
        CloseOutline,
    } from "flowbite-svelte-icons";

    let {
        isOpen = $bindable(false),
        relationships = $bindable([]),
        space_name,
        subpath,
        resource_type,
        parent_shortname,
    }: {
        isOpen: boolean;
        relationships: any[];
        space_name: string;
        subpath: string;
        resource_type: ResourceType;
        parent_shortname: string;
    } = $props();

    let isSaving = $state(false);

    // Form state
    let isEditing = $state(false);
    let editIndex = $state(-1);
    let showForm = $state(false);

    // Locator fields
    let relSpaceName = $state("");
    let relSubpath = $state("/");
    let relShortname = $state("");
    let relType = $state(ResourceType.content);
    let relSchemaShortname = $state("");

    // Attributes
    let relAttributes: any = $state({ json: {} });

    // Dropdown data
    let spaces: any[] = $state([]);
    let subpaths: string[] = $state([]);
    let shortnames: any[] = $state([]);
    let isLoadingSubpaths = $state(false);
    let isLoadingShortnames = $state(false);

    async function loadSpaces() {
        try {
            const result = await Dmart.getSpaces();
            spaces = result.records || [];
        } catch (e) {
            spaces = [];
        }
    }

    async function loadSubpaths(spaceName: string) {
        if (!spaceName) {
            subpaths = [];
            return;
        }
        isLoadingSubpaths = true;
        try {
            const tempSubpaths: string[] = [];
            const rootChildren = await getChildren(spaceName, "/", 100);
            await getChildrenAndSubChildren(
                tempSubpaths,
                spaceName,
                "",
                rootChildren,
            );
            subpaths = tempSubpaths.reverse();
        } catch (e) {
            subpaths = [];
        } finally {
            isLoadingSubpaths = false;
        }
    }

    async function loadShortnames(spaceName: string, subpathVal: string) {
        if (!spaceName || !subpathVal) {
            shortnames = [];
            return;
        }
        isLoadingShortnames = true;
        try {
            const result = await getChildren(spaceName, subpathVal, 100);
            shortnames = (result.records || []).filter(
                (r: any) => r.resource_type !== "folder",
            );
        } catch (e) {
            shortnames = [];
        } finally {
            isLoadingShortnames = false;
        }
    }

    $effect(() => {
        if (isOpen && spaces.length === 0) {
            loadSpaces();
        }
    });

    $effect(() => {
        if (relSpaceName) {
            loadSubpaths(relSpaceName);
            relSubpath = "/";
            relShortname = "";
            shortnames = [];
        }
    });

    $effect(() => {
        if (relSpaceName && relSubpath) {
            loadShortnames(relSpaceName, relSubpath);
            relShortname = "";
        }
    });

    function resetForm() {
        relSpaceName = "";
        relSubpath = "/";
        relShortname = "";
        relType = ResourceType.content;
        relSchemaShortname = "";
        relAttributes = { json: {} };
        isEditing = false;
        editIndex = -1;
        showForm = false;
    }

    function handleRenderMenu(items: any) {
        return items.filter(
            (item: any) => !["tree", "table"].includes(item.text),
        );
    }

    function populateFormForEdit(index: number) {
        const rel = relationships[index];
        const locator = rel.related_to || {};
        relSpaceName = locator.space_name || "";
        relSubpath = locator.subpath || "/";
        relShortname = locator.shortname || "";
        relType = locator.type || ResourceType.content;
        relSchemaShortname = locator.schema_shortname || "";
        relAttributes = { json: rel.attributes || {} };
        isEditing = true;
        editIndex = index;
        showForm = true;
    }

    function buildRelationship() {
        const locator: any = {
            type: relType,
            space_name: relSpaceName,
            subpath: relSubpath,
            shortname: relShortname,
        };
        if (relSchemaShortname) {
            locator.schema_shortname = relSchemaShortname;
        }

        let attrs = {};
        try {
            if (relAttributes?.json) {
                attrs = relAttributes.json;
            } else if (relAttributes?.text) {
                attrs = JSON.parse(relAttributes.text);
            }
        } catch {
            attrs = {};
        }

        return {
            related_to: locator,
            attributes: attrs,
        };
    }

    async function saveRelationships(updatedRelationships: any[]) {
        isSaving = true;
        try {
            await Dmart.request({
                space_name,
                request_type: RequestType.update,
                records: [
                    {
                        resource_type,
                        shortname: parent_shortname,
                        subpath,
                        attributes: {
                            relationships: updatedRelationships,
                        },
                    },
                ],
            });
            showToast(Level.info, "Relationships saved successfully!");
        } catch (e: any) {
            showToast(
                Level.warn,
                e.response?.data?.error?.message ||
                    "Failed to save relationships",
            );
        } finally {
            isSaving = false;
        }
    }

    async function addRelationship() {
        const rel = buildRelationship();
        if (!rel.related_to.space_name || !rel.related_to.shortname) return;

        let updated: any[];
        if (isEditing && editIndex >= 0) {
            updated = [...relationships];
            updated[editIndex] = rel;
        } else {
            updated = [...relationships, rel];
        }

        await saveRelationships(updated);
        relationships = updated;
        resetForm();
    }

    async function removeRelationship(index: number) {
        const updated = relationships.filter(
            (_: any, i: number) => i !== index,
        );
        await saveRelationships(updated);
        relationships = updated;
    }

    function getLocatorDisplay(rel: any) {
        const loc = rel.related_to || {};
        return `${loc.space_name || "?"}:${loc.subpath || "/"}/${loc.shortname || "?"}`;
    }
</script>

<Modal bind:open={isOpen} title="Manage Relationships">
    <div class="space-y-4 w-full">
        <!-- Existing relationships list -->
        {#if relationships && relationships.length > 0}
            <div class="space-y-2 w-full max-w-2xl mx-auto">
                {#each relationships as rel, index}
                    <Card class="p-3 w-full">
                        <div class="flex items-center justify-between">
                            <div class="flex-1">
                                <div class="flex items-center gap-2">
                                    <span
                                        class="inline-block px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800"
                                    >
                                        {rel.related_to?.type || "content"}
                                    </span>
                                    <span class="font-medium text-sm">
                                        {getLocatorDisplay(rel)}
                                    </span>
                                </div>
                                {#if rel.related_to?.schema_shortname}
                                    <p class="text-xs text-gray-500 mt-1">
                                        Schema: {rel.related_to
                                            .schema_shortname}
                                    </p>
                                {/if}
                                {#if rel.attributes && Object.keys(rel.attributes).length > 0}
                                    <p class="text-xs text-gray-400 mt-1">
                                        Attributes: {JSON.stringify(
                                            rel.attributes,
                                        ).substring(0, 80)}{JSON.stringify(
                                            rel.attributes,
                                        ).length > 80
                                            ? "..."
                                            : ""}
                                    </p>
                                {/if}
                            </div>
                            <div class="flex items-center gap-1">
                                <Button
                                    size="xs"
                                    color="light"
                                    onclick={() => populateFormForEdit(index)}
                                >
                                    <PenSolid size="sm" />
                                </Button>
                                <Button
                                    size="xs"
                                    color="light"
                                    onclick={() => removeRelationship(index)}
                                    disabled={isSaving}
                                >
                                    <TrashBinSolid
                                        size="sm"
                                        class="text-red-500"
                                    />
                                </Button>
                            </div>
                        </div>
                    </Card>
                {/each}
            </div>
        {:else}
            <p class="text-gray-500 text-center py-4">
                No relationships defined yet.
            </p>
        {/if}

        <!-- Toggle add form -->
        {#if !showForm}
            <div class="flex justify-center">
                <Button
                    color="blue"
                    outline
                    onclick={() => {
                        showForm = true;
                    }}
                >
                    <PlusOutline size="sm" class="mr-2" />
                    Add Relationship
                </Button>
            </div>
        {:else}
            <Card class="p-4 w-full max-w-2xl mx-auto">
                <div class="flex items-center justify-between mb-4">
                    <h4 class="text-lg font-semibold">
                        {isEditing ? "Edit Relationship" : "New Relationship"}
                    </h4>
                    <Button size="xs" color="light" onclick={resetForm}>
                        <CloseOutline size="sm" />
                    </Button>
                </div>

                <div class="space-y-3">
                    <!-- Space Name -->
                    <div>
                        <Label for="rel-space">Space Name</Label>
                        <Select id="rel-space" bind:value={relSpaceName}>
                            <option value="">-- Select Space --</option>
                            {#each spaces as space}
                                <option value={space.shortname}
                                    >{space.shortname}</option
                                >
                            {/each}
                        </Select>
                    </div>

                    <!-- Subpath -->
                    <div>
                        <Label for="rel-subpath">Subpath</Label>
                        <Select
                            id="rel-subpath"
                            bind:value={relSubpath}
                            disabled={!relSpaceName || isLoadingSubpaths}
                        >
                            <option value="/">/</option>
                            {#each subpaths as path}
                                <option value={path}>{path}</option>
                            {/each}
                        </Select>
                        {#if isLoadingSubpaths}
                            <p class="text-xs text-gray-400 mt-1">
                                Loading subpaths...
                            </p>
                        {/if}
                    </div>

                    <!-- Shortname -->
                    <div>
                        <Label for="rel-shortname">Shortname</Label>
                        <Select
                            id="rel-shortname"
                            bind:value={relShortname}
                            disabled={!relSpaceName || isLoadingShortnames}
                        >
                            <option value="">-- Select --</option>
                            {#each shortnames as item}
                                <option value={item.shortname}
                                    >{item.shortname}</option
                                >
                            {/each}
                        </Select>
                        {#if isLoadingShortnames}
                            <p class="text-xs text-gray-400 mt-1">
                                Loading entries...
                            </p>
                        {/if}
                    </div>

                    <!-- Resource Type -->
                    <div>
                        <Label for="rel-type">Resource Type</Label>
                        <Select id="rel-type" bind:value={relType}>
                            {#each Object.values(ResourceType) as rt}
                                <option value={rt}>{rt}</option>
                            {/each}
                        </Select>
                    </div>

                    <!-- Schema Shortname (optional) -->
                    <div>
                        <Label for="rel-schema"
                            >Schema Shortname (optional)</Label
                        >
                        <Input
                            id="rel-schema"
                            type="text"
                            bind:value={relSchemaShortname}
                            placeholder="Optional schema shortname"
                        />
                    </div>

                    <!-- Attributes JSON editor -->
                    <div>
                        <Label>Attributes</Label>
                        <div
                            class="border rounded-md overflow-hidden"
                            style="min-height: 120px;"
                        >
                            <JSONEditor
                                onRenderMenu={handleRenderMenu}
                                mode={Mode.text}
                                bind:content={relAttributes}
                            />
                        </div>
                    </div>

                    <!-- Actions -->
                    <div class="flex justify-end gap-2 pt-2">
                        <Button color="alternative" onclick={resetForm}
                            >Cancel</Button
                        >
                        <Button
                            color="blue"
                            onclick={addRelationship}
                            disabled={!relSpaceName ||
                                !relShortname ||
                                isSaving}
                        >
                            {#if isSaving}
                                Saving...
                            {:else}
                                {isEditing ? "Update" : "Add"}
                            {/if}
                        </Button>
                    </div>
                </div>
            </Card>
        {/if}
    </div>

    <div class="flex justify-end w-full pt-4 border-t mt-4">
        <Button
            color="alternative"
            onclick={() => {
                isOpen = false;
            }}>Close</Button
        >
    </div>
</Modal>
