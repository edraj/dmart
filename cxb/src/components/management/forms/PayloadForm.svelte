<script lang="ts">
    import {Label, Select} from "flowbite-svelte";
    import {ContentType, Dmart, QueryType, ResourceType,} from "@edraj/tsdmart";
    import FolderForm from "@/components/management/forms/FolderForm.svelte";
    import {JSONEditor, Mode} from "svelte-jsoneditor";
    import {currentEntry, InputMode, resourcesWithFormAndJson, resourceTypeWithNoPayload,} from "@/stores/global";
    import SchemaForm from "@/components/management/forms/SchemaForm.svelte";
    import WorkflowForm from "@/components/management/forms/WorkflowForm.svelte";
    import DynamicSchemaBasedForms from "@/components/management/forms/DynamicSchemaBasedForms.svelte";
    import TranslationForm from "@/components/management/forms/TranslationForm.svelte";
    import HtmlEditor from "@/components/management/editors/HtmlEditor.svelte";
    import MarkdownEditor from "@/components/management/editors/MarkdownEditor.svelte";
    import {fetchWorkflows} from "@/lib/dmart_services";
    import {params} from "@roxi/routify";
    import {untrack} from "svelte";
    import {generateObjectFromSchema} from "@/utils/renderer/rendererUtils";
    import {jsonEditorContentParser} from "@/utils/jsonEditor";

    let {
        isCreate = true,
        selectedResourceType = $bindable(),
        selectedSchema = $bindable(),
        contentType = $bindable(),
        selectedWorkflow = $bindable(),
        selectedInputMode = $bindable(),
        content = $bindable(),
        errorContent = $bindable(),
    } = $props();

    const subpath = $params.subpath;

    let contentTypeOptions = [
        { name: "JSON", value: "json" },
        { name: "HTML", value: "html" },
        { name: "Markdown", value: "markdown" },
        { name: "Text", value: "text" },
    ];

    function handleRenderMenu(items: any, _context: any) {
        items = items.filter(
            (item) => !["tree", "text", "table"].includes(item.text),
        );
        const separator = {
            separator: true,
        };

        const itemsWithoutSpace = items.slice(0, items.length - 2);
        return itemsWithoutSpace.concat([
            separator,
            {
                space: true,
            },
        ]);
    }

    let isFolderFormReady = $state(false);
    async function setFolderSchemaContent() {
        try {
            isFolderFormReady = false;
            const _schemaContent = await Dmart.retrieveEntry({
                resource_type: ResourceType.schema,
                space_name: "management",
                subpath: "schema",
                shortname: "folder_rendering",
                retrieve_json_payload: true,
                retrieve_attachments: false,
                validate_schema: true,
            });
            content = {
                json:
                    _schemaContent &&
                    generateObjectFromSchema(_schemaContent.payload.body),
            };
        } catch (e) {
            errorContent = e.response.data;
            isFolderFormReady = false;
        } finally {
            isFolderFormReady = true;
        }
    }

    $effect(() => {
        if (isCreate && selectedResourceType) {
            untrack(() => {
                isFolderFormReady = false;
                if (selectedResourceType === ResourceType.folder) {
                    setFolderSchemaContent();
                } else {
                    selectedSchema = null;
                    content = { json: {} };
                }
            });
        }
    });

    const folderPreference = $currentEntry?.entry?.payload?.body;

    let tmpSchemas = [];
    let selectedSchemaContent = $state(null);

    let mismatchedProperties = $derived.by(() => {
        if (
            !selectedSchemaContent?.properties ||
            !content ||
            typeof content !== "object" ||
            Array.isArray(content)
        ) {
            return [];
        }
        const schemaKeys = new Set(
            Object.keys(selectedSchemaContent.properties),
        );
        const payloadKeys = Object.keys(content);
        return payloadKeys.filter((key) => !schemaKeys.has(key));
    });

    if (!isCreate) {
        Dmart.query({
            space_name: $params.space_name,
            type: QueryType.search,
            subpath: "/schema",
            search: "@shortname:" + selectedSchema,
            retrieve_json_payload: true,
            limit: 100,
        }).then((schemas) => {
            if (schemas && schemas.records && schemas.records.length > 0) {
                tmpSchemas = schemas.records;
                const _schemaContent = tmpSchemas.find(
                    (t) => t.shortname === selectedSchema,
                );
                if (_schemaContent) {
                    selectedSchemaContent =
                        _schemaContent.attributes.payload.body;
                }
            } else {
                selectedSchemaContent = null;
            }
        });
    }
    if (selectedResourceType === ResourceType.folder) {
        Dmart.retrieveEntry({
            resource_type: ResourceType.schema,
            space_name: "management",
            subpath: "schema",
            shortname: "folder_rendering",
            retrieve_json_payload: true,
            retrieve_attachments: true,
            validate_schema: true,
        })
            .then((result) => {
                selectedSchema = "folder_rendering";
                selectedSchemaContent = result.payload.body;
                isFolderFormReady = true;
            })
            .catch((e) => {
                errorContent = e.response.data;
                isFolderFormReady = false;
            });
    }

    $effect(() => {
        if (contentType === ContentType.json) {
            if (tmpSchemas && selectedSchema) {
                untrack(async () => {
                    const _schemaContent = tmpSchemas.find(
                        (t) => t.shortname === selectedSchema,
                    );

                    if (_schemaContent === undefined) {
                        return;
                    } else {
                        selectedSchemaContent =
                            _schemaContent.attributes.payload.body;
                    }

                    if (isCreate) {
                        if (
                            selectedResourceType === ResourceType.content &&
                            selectedSchema === "translation"
                        ) {
                            content = {
                                json: [],
                            };
                        } else {
                            content = {
                                json:
                                    _schemaContent &&
                                    generateObjectFromSchema(
                                        selectedSchemaContent,
                                    ),
                            };
                        }
                    }
                });
            } else if (isCreate) {
                untrack(() => {
                    selectedSchemaContent = null;
                    content = { json: {} };
                });
            }
        }
    });

    function parseQuerySchemaResponse(schemas) {
        tmpSchemas = schemas.records;
        if (schemas === null) {
            return [
                {
                    name: "None",
                    value: null,
                },
            ];
        }
        let result = [];
        const _schemas = schemas.records.map((e) => e.shortname);
        if (selectedResourceType === ResourceType.folder) {
            result = ["folder_rendering", ..._schemas];
        } else {
            result = _schemas.filter(
                (e: any) => !["meta_schema", "folder_rendering"].includes(e),
            );
        }
        let r = result.map((e: any) => ({
            name: e,
            value: e,
        }));

        if (
            folderPreference &&
            folderPreference?.content_schema_shortnames?.length
        ) {
            r = r.filter((s) =>
                folderPreference.content_schema_shortnames.includes(s.value),
            );
        }

        r.unshift({
            name: "None",
            value: null,
        });
        return r;
    }

    $effect(() => {
        if (isCreate && contentType === ContentType.json) {
            if (selectedInputMode === InputMode.json) {
                untrack(() => {
                    content = {
                        text: JSON.stringify(
                            jsonEditorContentParser($state.snapshot(content)),
                            null,
                            2,
                        ),
                    };
                });
            } else if (selectedInputMode === InputMode.form) {
                untrack(() => {
                    content = {
                        json: jsonEditorContentParser($state.snapshot(content)),
                    };
                });
            }
        }
    });
</script>

{#if !resourceTypeWithNoPayload.includes(selectedResourceType)}
    {#if isCreate && !["workflows", "schema"].includes(subpath) && ![ResourceType.folder, ResourceType.role, ResourceType.permission].includes(selectedResourceType)}
        {#if selectedResourceType === ResourceType.content}
            <Label class="mt-3">
                Content Type
                <Select
                    class="mt-2"
                    items={contentTypeOptions}
                    value={contentType}
                    onchange={(e: any) => {
                        if (e.target.value !== "json") {
                            content = "";
                        } else {
                            content = { json: {} };
                        }
                        contentType = e.target.value;
                    }}
                />
            </Label>
        {/if}

        {#if contentType === "json" || selectedResourceType !== ResourceType.content}
            <Label class="mt-3">
                Schema
                {#await Dmart.query( { space_name: $params.space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 100 }, )}
                    <div role="status" class="max-w-sm animate-pulse">
                        <div
                            class="h-3 bg-gray-200 rounded-full dark:bg-gray-700 mx-2 my-2.5"
                        ></div>
                    </div>
                {:then schemas}
                    <Select
                        class="mt-2"
                        items={parseQuerySchemaResponse(schemas)}
                        bind:value={selectedSchema}
                    />
                {/await}
            </Label>
        {/if}
    {/if}
    {#if selectedResourceType === ResourceType.folder && isFolderFormReady}
        {#if selectedInputMode === InputMode.form}
            {#if isCreate}
                {#if content.json}
                    <FolderForm bind:content={content.json} />
                {/if}
            {:else}
                <FolderForm bind:content />
            {/if}
        {:else if isCreate && selectedInputMode === InputMode.json}
            <JSONEditor
                onRenderMenu={handleRenderMenu}
                mode={Mode.text}
                bind:content
            />
        {/if}
    {/if}

    {#if isCreate && selectedResourceType === ResourceType.ticket}
        <Label class="mt-3">
            Workflow shortname
            {#await fetchWorkflows($params.space_name)}
                <div role="status" class="max-w-sm animate-pulse">
                    <div
                        class="h-3 bg-gray-200 rounded-full dark:bg-gray-700 mx-2 my-2.5"
                    ></div>
                </div>
            {:then workflows}
                <Select
                    class="mt-2"
                    items={workflows.map((w) => ({
                        name: w.shortname,
                        value: w.shortname,
                    }))}
                    bind:value={selectedWorkflow}
                    placeholder="Select Workflow"
                />
            {/await}
        </Label>
    {/if}

    {#if selectedResourceType === ResourceType.schema}
        {#if selectedInputMode === InputMode.form}
            {#if isCreate}
                {#if content.json}
                    <SchemaForm bind:content={content.json} />
                {/if}
            {:else}
                <SchemaForm bind:content />
            {/if}
        {:else if isCreate && selectedInputMode === InputMode.json}
            <JSONEditor
                onRenderMenu={handleRenderMenu}
                mode={Mode.text}
                bind:content
            />
        {/if}
    {/if}

    {#if subpath === "workflows"}
        {#if selectedInputMode === InputMode.form}
            {#if isCreate}
                {#if content.json}
                    <WorkflowForm bind:content={content.json} />
                {/if}
            {:else}
                <WorkflowForm bind:content />
            {/if}
        {/if}
    {/if}

    <!--{#if selectedResourceType === ResourceType.content && selectedSchema === "configuration"}-->
    <!--    <ConfigForm bind:entries={content.json.items}/>-->
    {#if selectedResourceType === ResourceType.content && selectedSchema === "translation"}
        {#if selectedSchemaContent}
            {#if isCreate}
                <TranslationForm
                    bind:entries={content.json}
                    columns={Object.keys(
                        selectedSchemaContent.properties.items.items.properties,
                    )}
                />
            {:else}
                <TranslationForm
                    bind:entries={content}
                    columns={Object.keys(
                        selectedSchemaContent.properties.items.items.properties,
                    )}
                />
            {/if}
        {/if}
    {:else if selectedResourceType === ResourceType.content && contentType === "html"}
        <HtmlEditor bind:content />
    {:else if selectedResourceType === ResourceType.content && contentType === "markdown"}
        <MarkdownEditor bind:content />
    {:else if selectedResourceType === ResourceType.content && contentType === "text"}
        <textarea class="w-full h-full my-2" bind:value={content} />
    {:else}
        {#if !isCreate && mismatchedProperties.length > 0}
            <div
                class="bg-yellow-50 border-l-4 border-yellow-400 p-4 my-2 w-full mx-auto dark:bg-yellow-900/20 dark:border-yellow-500"
            >
                <div class="flex">
                    <div class="ml-3">
                        <p
                            class="text-sm text-yellow-700 font-medium dark:text-yellow-400"
                        >
                            ⚠ The current payload does not match the schema.
                        </p>
                        {#if selectedInputMode === InputMode.form}
                            <p
                                class="text-sm text-yellow-600 mt-1 dark:text-yellow-300"
                            >
                                The following properties will be discarded when
                                saving from form mode:
                            </p>
                            <ul
                                class="list-disc list-inside text-sm text-yellow-800 mt-1 dark:text-yellow-200"
                            >
                                {#each mismatchedProperties as prop}
                                    <li>
                                        <code
                                            class="bg-yellow-100 px-1 rounded dark:bg-yellow-800"
                                            >{prop}</code
                                        >
                                    </li>
                                {/each}
                            </ul>
                        {/if}
                    </div>
                </div>
            </div>
        {/if}
        <div class="my-2">
            {#if resourcesWithFormAndJson.includes(selectedResourceType)}
                {#if selectedInputMode === InputMode.form}
                    {#if selectedSchemaContent}
                        {#if isCreate}
                            {#if content.json}
                                <DynamicSchemaBasedForms
                                    schema={selectedSchemaContent}
                                    bind:content={content.json}
                                />
                            {/if}
                        {:else}
                            <DynamicSchemaBasedForms
                                schema={selectedSchemaContent}
                                bind:content
                            />
                        {/if}
                    {/if}
                {:else if isCreate && selectedInputMode === InputMode.json}
                    <JSONEditor
                        onRenderMenu={handleRenderMenu}
                        mode={Mode.text}
                        bind:content
                    />
                {/if}
            {/if}
        </div>
    {/if}
{/if}
