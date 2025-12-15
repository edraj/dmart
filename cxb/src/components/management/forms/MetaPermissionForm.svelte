<script lang="ts">
    import {
        Accordion,
        AccordionItem,
        Button,
        Card,
        Helper,
        Input,
        Label,
        Select,
        Spinner,
        Textarea
    } from 'flowbite-svelte';
    import {PlusOutline} from 'flowbite-svelte-icons';
    import {RequestType, ResourceType} from '@edraj/tsdmart';
    import {onMount} from "svelte";
    import {getChildren, getChildrenAndSubChildren, getSpaces} from "@/lib/dmart_services";
    import {Level, showToast} from "@/utils/toast";

    let {
        formData = $bindable(),
        validateFn = $bindable(),
        readOnly = false
    }: {
        formData: any,
        validateFn: () => boolean
        readOnly: boolean,
    } = $props();

    let form;

    formData = {
        ...formData,
        subpaths: formData.subpaths || {},
        resource_types: formData.resource_types || [],
        actions: formData.actions || [],
        conditions: formData.conditions || [],
        restricted_fields: formData.restricted_fields || [],
        allowed_fields_values: formData.allowed_fields_values || {},
        filter_fields_values: formData.filter_fields_values || ''
    };

    const resourceTypeOptions = Object.keys(ResourceType).map(key => ({
        name: key,
        value: ResourceType[key]
    }));

    const requestTypeOptions = Object.keys(RequestType).map(key => ({
        name: key,
        value: RequestType[key]
    }));
    requestTypeOptions.unshift({
        name: 'view',
        value: 'view',
    });
    requestTypeOptions.unshift({
        name: 'query',
        value: 'query',
    });

    let selectedResourceType = '';
    let selectedAction = '';
    let newCondition = '';
    let newRestrictedField = '';

    let spaces = $state([]);
    let subpaths = $state([]);
    let selectedSpace = $state('');
    let selectedSubpath = $state('');
    let loadingSpaces = $state(true);
    let loadingSubpaths = $state(false);

    onMount(async () => {
        try {
            const spacesResponse = await getSpaces();
            spaces = spacesResponse.records.map(space => ({ name: space.shortname, value: space.shortname }));
            spaces.unshift({
                name: '__all_spaces__',
                value: '__all_spaces__'
            });
        } catch (error) {
            console.error("Failed to load spaces:", error);
        } finally {
            loadingSpaces = false;
        }
    });


    function addResourceType() {
        if (selectedResourceType && !formData.resource_types.includes(selectedResourceType)) {
            formData.resource_types = [...formData.resource_types, selectedResourceType];
            selectedResourceType = '';
        }
    }

    function removeResourceType(item) {
        formData.resource_types = formData.resource_types.filter(i => i !== item);
    }

    function addAction() {
        if (selectedAction && !formData.actions.includes(selectedAction)) {
            formData.actions = [...formData.actions, selectedAction];
            selectedAction = '';
        }
    }

    function removeAction(item) {
        formData.actions = formData.actions.filter(i => i !== item);
    }

    function addCondition() {
        if (newCondition && !formData.conditions.includes(newCondition)) {
            formData.conditions = [...formData.conditions, newCondition];
            newCondition = '';
        }
    }

    function removeCondition(item) {
        formData.conditions = formData.conditions.filter(i => i !== item);
    }

    function addRestrictedField() {
        if (newRestrictedField && !formData.restricted_fields.includes(newRestrictedField)) {
            formData.restricted_fields = [...formData.restricted_fields, newRestrictedField];
            newRestrictedField = '';
        }
    }

    async function loadSubpaths(spaceName) {
        if (!spaceName) return;

        loadingSubpaths = true;
        try {
            const subpathsResponse = []
            const childSubpaths = await getChildren(spaceName, '/');
            await getChildrenAndSubChildren(subpathsResponse, spaceName, "", childSubpaths);
            subpaths = subpathsResponse.map(record => ({
                name: record,
                value: record
            }));
        } catch (error) {
            console.error("Failed to load subpaths:", error);
            subpaths = [];
        } finally {
            subpaths.unshift({
                name: '__all_subpaths__',
                value: '__all_subpaths__'
            });
            subpaths.unshift({
                name: '/',
                value: '/'
            });
            loadingSubpaths = false;
        }
    }

    function addSubpathToSpace() {
        if (!selectedSpace || !selectedSubpath) return;

        if (!formData.subpaths[selectedSpace]) {
            formData.subpaths[selectedSpace] = [];
        }

        if (!formData.subpaths[selectedSpace].includes(selectedSubpath)) {
            formData.subpaths[selectedSpace] = [
                ...formData.subpaths[selectedSpace],
                selectedSubpath
            ];
        }

        selectedSubpath = '';
    }

    function removeSubpath(space, subpath) {
        formData.subpaths[space] = formData.subpaths[space].filter(p => p !== subpath);

        // Remove the space key if no subpaths remain
        if (formData.subpaths[space].length === 0) {
            const { [space]: _, ...rest } = formData.subpaths;
            formData.subpaths = rest;
        }
    }

    function removeRestrictedField(item) {
        formData.restricted_fields = formData.restricted_fields.filter(i => i !== item);
    }

    let jsonEditorContent = '';

    function updateJsonEditor() {
        try {
            jsonEditorContent = JSON.stringify(formData.allowed_fields_values, null, 2);
        } catch (e) {
            jsonEditorContent = '{}';
        }
    }

    function saveJsonEditor() {
        try {
            formData.allowed_fields_values = JSON.parse(jsonEditorContent);
        } catch (e) {
            alert('Invalid JSON format');
        }
    }

    updateJsonEditor();

    function validate() {
        try {
            formData.allowed_fields_values = JSON.parse(jsonEditorContent);
        } catch (e) {
            showToast(Level.warn, 'Invalid JSON format in Allowed Fields Values', 'Please correct the JSON syntax.');
        }

        const isValid = form.checkValidity();

        if (!isValid) {
            form.reportValidity()
        }

        return isValid;
    }

    $effect(() => {
        validateFn = validate;
    });

    $effect(() => {
        if (selectedSpace) {
            loadSubpaths(selectedSpace);
        }
    });

    let subpathEntries: any = $derived(Object.entries(formData.subpaths));
</script>

<Card class="w-full max-w-4xl mx-auto p-4  my-2">
    <h2 class="text-2xl font-bold mb-4">Permission Settings</h2>

    <form bind:this={form} class="space-y-4">
        <div class="mb-4">
            <Label class="mb-2">
                Resource Types
            </Label>
            {#if !readOnly}
                <div class="flex space-x-2">
                    <Select
                            class="flex-grow"
                            placeholder="Select resource type"
                            items={resourceTypeOptions}
                            bind:value={selectedResourceType} />
                    <Button class="bg-primary" size="sm" onclick={addResourceType}>
                        <PlusOutline size="md" />
                    </Button>
                </div>
            {/if}

            {#if formData.resource_types.length > 0}
                <div class="mt-2 flex flex-wrap gap-2">
                    {#each formData.resource_types as item}
                        <div class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full flex items-center">
                            <span>{item}</span>
                            {#if !readOnly}
                                <button class="ml-2 text-blue-600" type="button" onclick={() => removeResourceType(item)}>
                                    ×
                                </button>
                            {/if}
                        </div>
                    {/each}
                </div>
            {:else}
                <div class="mt-2 p-2 border border-dashed rounded-lg text-center text-gray-500">
                    No resource types added
                </div>
            {/if}
        </div>

        <div class="mb-4">
            <Label class="mb-2">
                Actions
            </Label>
            {#if !readOnly}
                <div class="flex space-x-2">
                    <Select
                            class="flex-grow"
                            placeholder="Select action"
                            items={requestTypeOptions}
                            bind:value={selectedAction} />
                    <Button class="bg-primary" size="sm" onclick={addAction}>
                        <PlusOutline size="md" />
                    </Button>
                </div>
            {/if}

            {#if formData.actions.length > 0}
                <div class="mt-2 flex flex-wrap gap-2">
                    {#each formData.actions as item}
                        <div class="bg-green-100 text-green-800 px-3 py-1 rounded-full flex items-center">
                            <span>{item}</span>
                            {#if !readOnly}
                                <button class="ml-2 text-green-600" type="button" onclick={() => removeAction(item)}>
                                    ×
                                </button>
                            {/if}
                        </div>
                    {/each}
                </div>
            {:else}
                <div class="mt-2 p-2 border border-dashed rounded-lg text-center text-gray-500">
                    No actions added
                </div>
            {/if}
        </div>

        <Accordion>
            <AccordionItem>
                {#snippet header()}
        <span>
            Subpaths
        </span>
                {/snippet}
                <div class="p-4 space-y-4">
                    {#if !readOnly}
                        <div class="mb-4">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <Label class="mb-2">Space</Label>
                                    {#if loadingSpaces}
                                        <div class="flex items-center gap-2">
                                            <Spinner size="4" />
                                            <span class="text-gray-500">Loading spaces...</span>
                                        </div>
                                    {:else}
                                        <Select
                                                class="flex-grow"
                                                placeholder="Select space"
                                                items={spaces}
                                                bind:value={selectedSpace}
                                        />
                                    {/if}
                                </div>

                                <div>
                                    <Label class="mb-2">Subpath</Label>
                                    {#if loadingSubpaths}
                                        <div class="flex items-center gap-2">
                                            <Spinner size="4" />
                                            <span class="text-gray-500">Loading subpaths...</span>
                                        </div>
                                    {:else}
                                        <div class="flex space-x-2">
                                            <Select
                                                    class="flex-grow"
                                                    placeholder="Select subpath"
                                                    items={subpaths}
                                                    bind:value={selectedSubpath}
                                                    disabled={!selectedSpace}
                                            />
                                            <Button class="bg-primary" size="sm" onclick={addSubpathToSpace} disabled={!selectedSpace || !selectedSubpath}>
                                                <PlusOutline size="md" />
                                            </Button>
                                        </div>
                                    {/if}
                                </div>
                            </div>
                        </div>
                    {/if}
                    {#if Object.keys(formData.subpaths).length > 0}
                        <div class="mt-4 border rounded-lg p-4 bg-gray-50">
                            {#each subpathEntries as [space, paths]}
                                <div class="mb-4">
                                    <div class="font-medium text-gray-700 mb-2">{space}</div>
                                    <div class="flex flex-wrap gap-2">
                                        {#each paths as path}
                                            <div class="bg-purple-100 text-purple-800 px-3 py-1 rounded-full flex items-center">
                                                <span>{path}</span>
                                                {#if !readOnly}
                                                    <button
                                                            class="ml-2 text-purple-600 hover:text-purple-800"
                                                            type="button"
                                                            onclick={() => removeSubpath(space, path)}
                                                    >
                                                        ×
                                                    </button>
                                                {/if}
                                            </div>
                                        {/each}
                                    </div>
                                </div>
                            {/each}
                        </div>
                    {:else}
                        <div class="mt-2 p-4 border border-dashed rounded-lg text-center text-gray-500">
                            No spaces or subpaths added
                        </div>
                    {/if}
                </div>
            </AccordionItem>

            <AccordionItem>
                {#snippet header()}<span>Conditions</span>{/snippet}
                <div class="p-4 space-y-4">
                    <div class="mb-4">
                        {#if !readOnly}
                            <div class="flex space-x-2">
                                <Select
                                        class="flex-grow"
                                        placeholder="Select condition"
                                        items={[
                                            { name: "own", value: "own" },
                                            { name: "is_active", value: "is_active" }
                                        ]}
                                        bind:value={newCondition} />
                                <Button class="bg-primary" size="sm" onclick={addCondition}>
                                    <PlusOutline size="md" />
                                </Button>
                            </div>
                        {/if}

                        {#if formData.conditions.length > 0}
                            <div class="mt-2 flex flex-wrap gap-2">
                                {#each formData.conditions as item}
                                    <div class="bg-yellow-100 text-yellow-800 px-3 py-1 rounded-full flex items-center">
                                        <span>{item}</span>
                                        {#if !readOnly}
                                            <button class="ml-2 text-yellow-600" type="button" onclick={() => removeCondition(item)}>
                                                ×
                                            </button>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="mt-2 p-2 border border-dashed rounded-lg text-center text-gray-500">
                                No conditions added
                            </div>
                        {/if}
                    </div>
                </div>
            </AccordionItem>

            <AccordionItem>
                {#snippet header()}
                    <span>
                        Restricted Fields
                    </span>
                {/snippet}
                <div class="p-4 space-y-4">
                    <div class="mb-4">
                        {#if !readOnly}
                            <div class="flex space-x-2">
                                <Input placeholder="Add restricted field" bind:value={newRestrictedField} />
                                <Button class="bg-primary" size="sm" onclick={addRestrictedField}>
                                    <PlusOutline size="md" />
                                </Button>
                            </div>
                        {/if}

                        {#if formData.restricted_fields.length > 0}
                            <div class="mt-2 flex flex-wrap gap-2">
                                {#each formData.restricted_fields as item}
                                    <div class="bg-red-100 text-red-800 px-3 py-1 rounded-full flex items-center">
                                        <span>{item}</span>
                                        {#if !readOnly}
                                            <button class="ml-2 text-red-600" type="button" onclick={() => removeRestrictedField(item)}>
                                                ×
                                            </button>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="mt-2 p-2 border border-dashed rounded-lg text-center text-gray-500">
                                No restricted fields added
                            </div>
                        {/if}
                    </div>
                </div>
            </AccordionItem>

            <AccordionItem>
                {#snippet header()}
                    <span>
                        Allowed Fields Values
                    </span>
                {/snippet}
                <div class="p-4 space-y-4">
                    <div class="mb-4">
                        <Label>JSON Editor</Label>
                        <Helper class="mb-2">Edit the JSON object directly</Helper>
                        <div class="flex flex-col">
                            <Textarea
                                    rows={10}
                                    class="font-mono"
                                    bind:value={jsonEditorContent}
                            />
                            <div class="flex justify-end mt-2">
                                <Button size="sm" onclick={saveJsonEditor}>Apply Changes</Button>
                            </div>
                        </div>
                    </div>
                </div>
            </AccordionItem>

            <AccordionItem>
                {#snippet header()}
                    <span>
                        Filter Fields Values
                    </span>
                {/snippet}
                <div class="p-4 space-y-4">
                    <div class="mb-4">
                        <Label>Filter Fields Values</Label>
                        <Helper class="mb-2">Optional string to filter field values</Helper>
                        <Input
                            placeholder="Enter filter fields values"
                            bind:value={formData.filter_fields_values}
                            disabled={readOnly}
                        />
                    </div>
                </div>
            </AccordionItem>
        </Accordion>
    </form>
</Card>