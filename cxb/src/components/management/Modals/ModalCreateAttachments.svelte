<script lang="ts">
    import {Alert, Button, Fileupload, Label, Modal, Select, Textarea} from "flowbite-svelte";
    import {ContentType, Dmart, QueryType, RequestType, ResourceAttachmentType, ResourceType} from "@edraj/tsdmart";
    import {JSONEditor, Mode} from "svelte-jsoneditor";
    import HtmlEditor from "@/components/management/editors/HtmlEditor.svelte";
    import MarkdownEditor from "@/components/management/editors/MarkdownEditor.svelte";
    import {Level, showToast} from "@/utils/toast";
    import {jsonToFile} from "@/utils/jsonToFile";
    import {currentEntry} from "@/stores/global";
    import {jsonEditorContentParser} from "@/utils/jsonEditor";
    import Prism from "@/components/Prism.svelte";
    import {removeEmpty} from "@/utils/compare";
    import MetaForm from "@/components/management/forms/MetaForm.svelte";
    import {untrack} from "svelte";

    let {
        meta = $bindable({}),
        payload = $bindable({}),
        isOpen = $bindable(false),
        isUpdateMode = $bindable(false),
        selectedAttachment = $bindable(null),
        space_name = $bindable(""),
        parentResourceType,
        subpath = $bindable(""),
        parent_shortname = $bindable(""),
    } = $props();

    let resourceType = $state(ResourceAttachmentType.media);
    let contentType = $state(ContentType.image);
    let payloadFiles = $state<FileList | null>(null);
    let content: any = $state(payload);
    let selectedSchema = $state("");
    let trueResourceType = $state(null);
    let isLoading = $state(false);
    let errorModalMessage = $state(null);
    let errorContent = $state(null);


    $effect(() => {
        if (isOpen && selectedAttachment && isUpdateMode) {
            initializeFormWithAttachment(selectedAttachment);
        } else if (!isOpen) {
            resetModal();
        }
    });

    function initializeFormWithAttachment(attachment) {
        if (!attachment) return;

        const _attachment = structuredClone($state.snapshot(attachment));

        meta = {
            shortname: _attachment.shortname,
            is_active: _attachment.attributes.is_active,
            displayname: _attachment.attributes.displayname,
            description: _attachment.attributes.description,
        };

        if (_attachment.resource_type === ResourceType.json ||
            (_attachment.resource_type === ResourceType.media &&
                [ContentType.text, ContentType.json, ContentType.markdown, ContentType.html].includes(_attachment?.attributes?.payload?.content_type)) ||
            _attachment.resource_type === ResourceType.comment) {

            resourceType = ResourceAttachmentType[_attachment.resource_type];
            contentType = _attachment?.attributes?.payload?.content_type;

            if (_attachment.resource_type === ResourceType.json) {
                content = {json: _attachment.attributes.payload.body};
            } else {
                if (typeof _attachment.attributes.payload.body === 'string') {
                    content = _attachment.attributes.payload.body;
                } else {
                    content = {body: _attachment.attributes.payload.body};
                }
            }
        } else {
            trueResourceType = ResourceAttachmentType[_attachment.resource_type];
            resourceType = trueResourceType;

            const metaAttachment = structuredClone(_attachment);
            if (metaAttachment?.attributes?.payload?.body) {
                delete metaAttachment.attributes.payload.body;
            }
            content = {json: metaAttachment, text: undefined};
        }
    }

    function resetModal() {
        resourceType = ResourceAttachmentType.media;
        contentType = ContentType.image;
        payloadFiles = null;
        content = {};
        selectedSchema = "";
        meta = {
            shortname: "",
            is_active: true,
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
    }

    async function upload(event) {
        event.preventDefault();
        isLoading = true;
        errorModalMessage = null;
        errorContent = null;

        try {
            if (isUpdateMode && resourceType === ResourceAttachmentType.json && trueResourceType !== null) {
                await updateMeta();
                return;
            }
            let response;
            if (resourceType == ResourceAttachmentType.comment) {
                response = await Dmart.request({
                    space_name,
                    request_type: isUpdateMode
                        ? RequestType.update
                        : RequestType.create,
                    records: [
                        removeEmpty({
                            resource_type: ResourceType.comment,
                            shortname: meta.shortname,
                            subpath: `${subpath}/${parent_shortname}`.replaceAll("//", "/"),
                            attributes: {
                                displayname: meta.displayname,
                                description: meta.description,
                                is_active: true,
                                payload: {
                                    content_type: ContentType.json,
                                    body: {
                                        state: "commented",
                                        body: isUpdateMode ? content.body : content
                                    }
                                }
                            },
                        }),
                    ],
                });
            } else if (
                [
                    ResourceAttachmentType.csv,
                    ResourceAttachmentType.jsonl,
                    ResourceAttachmentType.sqlite,
                    ResourceAttachmentType.parquet,
                ].includes(resourceType)
            ) {
                response = await Dmart.uploadWithPayload(
                    {
                        space_name,
                        subpath: parentResourceType === ResourceType.folder ? subpath : subpath + "/" + parent_shortname,
                        shortname: meta.shortname,
                        resource_type: ResourceType[resourceType],
                        payload_file: ResourceType[resourceType] === ResourceType.json
                            ? jsonToFile(content)
                            : payloadFiles[0],
                        attributes: {
                            displayname: meta.displayname,
                            description: meta.description,
                            is_active: true,
                            payload: {
                                content_type: ContentType[resourceType],
                                schema_shortname: selectedSchema,
                                body: {}
                            },
                        }
                    }
                );
            } else if (
                [
                    ContentType.image,
                    ContentType.pdf,
                    ContentType.audio,
                    ContentType.video,
                    ContentType.apk,
                ].includes(contentType)
            ) {
                response = await Dmart.uploadWithPayload(
                    {
                        space_name,
                        subpath: parentResourceType === ResourceType.folder ? subpath : subpath + "/" + parent_shortname,
                        shortname: meta.shortname,
                        resource_type: ResourceType[resourceType],
                        payload_file: ResourceType[resourceType] === ResourceType.json
                            ? jsonToFile(content)
                            : payloadFiles[0],
                        attributes: removeEmpty({
                            displayname: meta.displayname,
                            description: meta.description,
                            is_active: true,
                            payload: {
                                content_type: contentType,
                                body: {}
                            },
                        })
                    }
                );
            } else if (
                [
                    ContentType.json,
                    ContentType.text,
                    ContentType.html,
                    ContentType.markdown,
                    ContentType,
                ].includes(contentType)
            ) {
                response = await Dmart.request({
                    space_name,
                    request_type: isUpdateMode
                        ? RequestType.update
                        : RequestType.create,
                    records: [
                        removeEmpty({
                            resource_type: ResourceType[resourceType],
                            shortname: meta.shortname,
                            subpath: parentResourceType === ResourceType.folder ? subpath : `${subpath}/${parent_shortname}`,
                            attributes: {
                                displayname: meta.displayname,
                                description: meta.description,
                                is_active: true,
                                payload: {
                                    content_type: contentType,
                                    schema_shortname:
                                        resourceType == ResourceAttachmentType.json && selectedSchema
                                            ? selectedSchema
                                            : null,
                                    body:
                                        resourceType == ResourceAttachmentType.json
                                            ? jsonEditorContentParser($state.snapshot(content))
                                            : content,
                                },
                            },
                        }),
                    ],
                });
            }

            if (response.status === "success") {
                showToast(Level.info);
                isOpen = false;
                resetModal();
                $currentEntry.refreshEntry();
            } else {
                showToast(Level.warn);
            }
        } catch (e) {
            console.log(e)
            showToast(Level.warn, e.response.data);
            errorContent = e.response.data;
        } finally {
            isLoading = false;
        }
    }

    function handleRenderMenu(menuItems) {
        return menuItems;
    }

    let validateMetaForm;

    async function updateMeta() {
        errorModalMessage = null;
        errorContent = null;
        let _payloadContent = jsonEditorContentParser($state.snapshot(content));

        _payloadContent.subpath = parentResourceType === ResourceType.folder ? subpath : `${subpath}/${parent_shortname}`;
        _payloadContent.attributes.displayname = meta.displayname
        _payloadContent.attributes.description = meta.description
        const request_dict = {
            space_name,
            request_type: RequestType.update,
            records: [removeEmpty(_payloadContent)],
        };

        try {
            const response = await Dmart.request(request_dict);
            if (response.status === "success") {
                showToast(Level.info);
                isOpen = false;
                resetModal();
                $currentEntry.refreshEntry();
            } else {
                showToast(Level.warn);
            }
        } catch (e) {
            showToast(Level.warn, e.response?.data || "Error updating metadata");
            errorContent = e.response?.data || "Error updating metadata";
        } finally {
            isLoading = false;
        }
    }

    $effect(() => {
        if (!isUpdateMode && resourceType) {
            if (resourceType === ResourceAttachmentType.json) {
                untrack(() => {
                    contentType = ContentType.json;
                    content = {json: {}};
                })
            } else if (resourceType === ResourceAttachmentType.comment) {
                untrack(() => {
                    content = "";
                })
            } else if (resourceType === ResourceAttachmentType.media) {
                untrack(() => {
                    contentType = ContentType.image;
                    content = "";
                })
            } else {
                untrack(() => {
                    content = {};
                })
            }
        }
    });
</script>

<Modal bind:open={isOpen} size="xl">
    <form onsubmit={upload}>
        <div class="flex justify-between items-center px-4 pt-4 border-b rounded-t">
            <h3 class="text-xl font-semibold text-gray-900">
                {#if isUpdateMode}
                    {#if resourceType === ResourceAttachmentType.json && trueResourceType !== null}
                        Edit Attachment Metadata
                    {:else}
                        Edit Attachment Content
                    {/if}
                {:else}
                    Add Attachment
                {/if}
            </h3>
        </div>

        <div class="p-4 max-h-[75vh] overflow-y-auto">
            {#if errorModalMessage}
                <Alert color="red">
                    <span class="font-medium">{errorModalMessage}</span>
                </Alert>
            {/if}
            <div class="flex flex-col space-y-4">
                <MetaForm bind:formData={meta} bind:validateFn={validateMetaForm} isCreate={!isUpdateMode}/>

                <div>
                    <Label for="resourceType">Attachment Type</Label>
                    <Select id="resourceType" bind:value={resourceType} disabled={isUpdateMode}>
                        {#each Object.values(ResourceAttachmentType).filter(type => type !== ResourceAttachmentType.alteration) as type}
                            <option value={type}>{type}</option>
                        {/each}
                    </Select>
                </div>
                {resourceType}
                {#if resourceType === ResourceAttachmentType.media}
                    <div>
                        <Label for="contentType">Content Type</Label>
                        <Select id="contentType" bind:value={contentType} disabled={isUpdateMode}>
                            {#each Object.values(ContentType).filter(c => ![ContentType.json, ContentType.csv, ContentType.jsonl, ContentType.sqlite, ContentType.parquet].includes(c)) as type}
                                <option value={type}>{type}</option>
                            {/each}
                        </Select>
                    </div>

                    <hr class="my-4"/>

                    {#if contentType === ContentType.image}
                        <div>
                            <Label for="imageFile">Image File</Label>
                            <Fileupload id="imageFile" type="file" accept="image/png, image/jpeg, image/webp" clearable
                                        bind:files={payloadFiles}/>
                        </div>
                    {:else if contentType === ContentType.pdf}
                        <div>
                            <Label for="pdfFile">PDF File</Label>
                            <Fileupload id="pdfFile" type="file" accept="application/pdf" clearable
                                        bind:files={payloadFiles}/>
                        </div>
                    {:else if contentType === ContentType.apk}
                        <div>
                            <Label for="apkFile">APK File</Label>
                            <Fileupload id="apkFile" type="file" accept=".apk" clearable bind:files={payloadFiles}/>
                        </div>
                    {:else if contentType === ContentType.audio}
                        <div>
                            <Label for="audioFile">Audio File</Label>
                            <Fileupload id="audioFile" type="file" accept="audio/*" clearable
                                        bind:files={payloadFiles}/>
                        </div>
                    {:else if contentType === ContentType.python}
                        <div>
                            <Label for="pythonFile">Python File</Label>
                            <Fileupload id="pythonFile" type="file" accept=".py" clearable bind:files={payloadFiles}/>
                        </div>
                    {:else if contentType === ContentType.markdown}
                        <div>
                            <MarkdownEditor bind:content={content}/>
                        </div>
                    {:else if contentType === ContentType.html}
                        <div>
                            <HtmlEditor bind:content={content}/>
                        </div>
                    {:else}
                        <div>
                            <Textarea bind:value={content}/>
                        </div>
                    {/if}
                {:else if resourceType === ResourceAttachmentType.json}
                    {#if content.json || content.text}
                        <div>
                            <JSONEditor onRenderMenu={handleRenderMenu} mode={Mode.text} bind:content={content}/>
                        </div>
                    {/if}
                {:else if resourceType === ResourceAttachmentType.comment}
                    <div>
                        {#if isUpdateMode}
                            <Textarea bind:value={content.body}/>
                        {:else }
                            <Textarea bind:value={content}/>
                        {/if}
                    </div>
                {:else if resourceType === ResourceAttachmentType.csv}
                    <div>
                        <Label for="csvFile">CSV File</Label>
                        <Fileupload id="csvFile" type="file" accept=".csv" clearable bind:files={payloadFiles}/>

                        <div class="mt-3">
                            <Label for="csvSchema">Schema</Label>
                            <Select id="csvSchema" bind:value={selectedSchema} disabled={isUpdateMode}>
                                <option value="">None</option>
                                {#await Dmart.query({
                                    space_name,
                                    type: QueryType.search,
                                    subpath: "/schema",
                                    search: "",
                                    retrieve_json_payload: true,
                                    limit: 99
                                }) then schemas}
                                    {#each schemas.records.map(e => e.shortname) as schema}
                                        <option value={schema}>{schema}</option>
                                    {/each}
                                {/await}
                            </Select>
                        </div>
                    </div>
                {:else if resourceType === ResourceAttachmentType.jsonl}
                    <div>
                        <Label for="jsonlFile">JSONL File</Label>
                        <Fileupload id="jsonlFile" type="file" accept=".jsonl" clearable bind:files={payloadFiles}/>
                    </div>
                {:else if resourceType === ResourceAttachmentType.sqlite}
                    <div>
                        <Label for="sqliteFile">SQLite File</Label>
                        <Fileupload id="sqliteFile" type="file" accept=".sqlite,.sqlite3,.db,.db3,.s3db,.sl3" clearable
                                    bind:files={payloadFiles}/>
                    </div>
                {:else if resourceType === ResourceAttachmentType.parquet}
                    <div>
                        <Label for="parquetFile">Parquet File</Label>
                        <Fileupload id="parquetFile" type="file" accept=".parquet" clearable bind:files={payloadFiles}/>
                    </div>
                {/if}
            </div>

            {#if errorContent}
                <div class="mt-3">
                    <Prism code={errorContent} language={"json"}/>
                </div>
            {/if}
        </div>

        <div class="flex justify-end space-x-2 p-4 border-t">
            <Button color="alternative" onclick={()=>{isOpen=false}} disabled={isLoading}>
                Cancel
            </Button>
            <Button color="blue" type="submit" class={isLoading ? "cursor-not-allowed" : "cursor-pointer"}
                    disabled={isLoading}>
                {#if isLoading}
                    {isUpdateMode ? "Updating..." : "Uploading..."}
                {:else}
                    {#if isUpdateMode}
                        {#if resourceType === ResourceAttachmentType.json && trueResourceType !== null}
                            Update Metadata
                        {:else}
                            Update Content
                        {/if}
                    {:else}
                        Upload
                    {/if}
                {/if}
            </Button>
        </div>
    </form>
</Modal>
