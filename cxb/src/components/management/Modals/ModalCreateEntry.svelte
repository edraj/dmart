<script lang="ts">
    import {Alert, Button, Label, Modal, Select, Spinner} from "flowbite-svelte";
    import {CodeOutline, FileCodeOutline} from "flowbite-svelte-icons";
    import {Dmart, RequestType, ResourceType} from "@edraj/tsdmart";
    import {tick, untrack} from "svelte";
    import {scrollToElById} from "@/utils/renderer/rendererUtils";
    import Prism from "@/components/Prism.svelte";
    import MetaForm from "@/components/management/forms/MetaForm.svelte";
    import MetaUserForm from "@/components/management/forms/MetaUserForm.svelte";
    import {jsonEditorContentParser} from "@/utils/jsonEditor";
    import {currentEntry, currentListView, InputMode, resourcesWithFormAndJson, spaceChildren,} from "@/stores/global";
    import MetaRoleForm from "@/components/management/forms/MetaRoleForm.svelte";
    import MetaPermissionForm from "@/components/management/forms/MetaPermissionForm.svelte";
    import {Level, showToast} from "@/utils/toast";
    import {checkAccess} from "@/utils/checkAccess";
    import PayloadForm from "@/components/management/forms/PayloadForm.svelte";
    import {removeEmpty} from "@/utils/compare";

    let {
        space_name,
        subpath,
        isOpen=$bindable(false),
    }:{
        space_name:string,
        subpath:string
        isOpen:boolean,
    } = $props();

    const folderPreference = $currentEntry?.entry?.payload?.body;

    let selectedResourceType = $state(ResourceType.content);
    let allowedResourceTypes = $state([]);

    let selectedInputMode = $state(InputMode.form);

    function setAllowedResourceTypes(){
        if (space_name === "management"){
            if (subpath === "users") {
                if(checkAccess('create', "management", "users", ResourceType.user)) {
                    allowedResourceTypes = [
                        {
                            name: ResourceType.user.toString(),
                            value: ResourceType.user,
                        }
                    ];
                    return;
                }
            }
            else if (subpath === "roles") {
                if(checkAccess('create', "management", "roles", ResourceType.role)) {
                    allowedResourceTypes = [
                        {
                            name: ResourceType.role.toString(),
                            value: ResourceType.role,
                        }
                    ];
                    return;
                }
            }
            else if (subpath === "permissions") {
                if(checkAccess('create', "management", "permissions", ResourceType.permission)) {
                    allowedResourceTypes = [
                        {
                            name: ResourceType.permission.toString(),
                            value: ResourceType.permission,
                        }
                    ];
                    return;
                }
            }
            else {
                allowedResourceTypes = [
                    {
                        name: ResourceType.content.toString(),
                        value: ResourceType.content,
                    }
                ];
            }
        }
        if (subpath === "schema") {
            if(checkAccess('create', space_name, "schema", ResourceType.schema)) {
                allowedResourceTypes = [
                    {
                        name: ResourceType.schema.toString(),
                        value: ResourceType.schema,
                    }
                ];
                return;
            }
        }
        else if (subpath === "workflows") {
            if(checkAccess('create', space_name, "workflows", ResourceType.content)) {
                allowedResourceTypes = [
                    {
                        name: ResourceType.content.toString(),
                        value: ResourceType.content,
                    }
                ];
                return;
            }
        }
        else {
            allowedResourceTypes = [];
            if(checkAccess('create', space_name, subpath, ResourceType.content)) {
                allowedResourceTypes = [
                    ...allowedResourceTypes,
                    {
                        name: ResourceType.content.toString(),
                        value: ResourceType.content,
                    }
                ];
            }
            if(checkAccess('create', space_name, subpath, ResourceType.ticket)) {
                allowedResourceTypes = [
                    ...allowedResourceTypes,
                    {
                        name: ResourceType.ticket.toString(),
                        value: ResourceType.ticket,
                    }
                ];
            }
            if(checkAccess('create', space_name, subpath, ResourceType.folder)) {
                allowedResourceTypes = [
                    ...allowedResourceTypes,
                    {
                        name: ResourceType.folder.toString(),
                        value: ResourceType.folder,
                    }
                ];
            }
        }
    }
    function prepareResourceTypes() {
        setAllowedResourceTypes()

        if(folderPreference && folderPreference?.content_resource_types?.length) {
            allowedResourceTypes = allowedResourceTypes.filter(rt => folderPreference.content_resource_types.includes(rt.value));
        }
        selectedResourceType = allowedResourceTypes[0].value;
    }
    prepareResourceTypes();

    let selectedSchema = $state(null);


    let content: any = $state({
        json: {}
    });
    let metaContent: any = $state({});
    let contentType = $state("json");

    let errorContent: any = $state(null);
    let validateMetaForm;
    let validateRTForm;

    let isHandleCreateEntryLoading = $state(false);
    let errorModalMessage = $state(null);
    async function handleCreateEntry() {
        errorModalMessage = null;
        if (!validateMetaForm()) {
            errorModalMessage = "Please fill all required fields in the meta form.";
            return;
        }

        if([ResourceType.user, ResourceType.role, ResourceType.permission].includes(selectedResourceType)){
            if (!validateRTForm()) {
                errorModalMessage = "Please fill all required fields in the respective resource type form.";
                return;
            }
        }

        try {
            isHandleCreateEntryLoading = true;
            let response = null;
            const _metaContent = $state.snapshot(metaContent);
            const shortname = _metaContent.shortname;
            delete _metaContent.shortname;

            const requestCreate: any = {
                "resource_type": selectedResourceType,
                "shortname": shortname,
                "subpath": subpath,
                "attributes": {
                    ..._metaContent
                },
            }
            if(selectedResourceType === ResourceType.ticket) {
                requestCreate.attributes = {
                    ...requestCreate.attributes,
                    workflow_shortname: selectedWorkflow,
                    payload: {
                        body: jsonEditorContentParser($state.snapshot(content)),
                        schema_shortname: selectedSchema,
                        content_type: "json"
                    }
                };
            }
            else if(selectedResourceType === ResourceType.schema) {
                requestCreate.attributes = {
                    ...requestCreate.attributes,
                    payload: {
                        body: jsonEditorContentParser($state.snapshot(content)),
                        schema_shortname: 'meta_schema',
                        content_type: "json"
                    }
                };
            }
            else if(selectedResourceType === ResourceType.content && subpath === "workflows") {
                requestCreate.attributes = {
                    ...requestCreate.attributes,
                    payload: {
                        body: jsonEditorContentParser($state.snapshot(content)),
                        schema_shortname: 'workflow',
                        content_type: "json"
                    }
                };
            }
            else if(selectedResourceType === ResourceType.content) {
                requestCreate.attributes = {
                    ...requestCreate.attributes,
                    payload: {
                        body: jsonEditorContentParser($state.snapshot(content)),
                        schema_shortname: contentType === "json" ? selectedSchema : null,
                        content_type: contentType
                    }
                };
            } else if(selectedSchema) {
                requestCreate.attributes = {
                    ...requestCreate.attributes,
                    payload: {
                        body: jsonEditorContentParser($state.snapshot(content)),
                        schema_shortname: selectedSchema,
                        content_type: "json"
                    }
                };
            } else {
                requestCreate.attributes = {
                    ...requestCreate.attributes,
                    payload: {
                        body: jsonEditorContentParser($state.snapshot(content)),
                        schema_shortname: null,
                        content_type: "json"
                    }
                };
                if(requestCreate.attributes.payload === null && requestCreate.attributes.schema_shortname === null){
                    delete requestCreate.attributes.payload;
                }
            }

            const request = {
                space_name,
                request_type: RequestType.create,
                records: [{
                    resource_type: selectedResourceType,
                    subpath: subpath,
                    shortname: metaContent.shortname,
                    attributes: removeEmpty(requestCreate.attributes)
                }]
            }
            response = await Dmart.request(request);

            if (response.attributes && response.attributes.error) {
                isHandleCreateEntryLoading = false;
                errorContent = response.attributes.error;
                return;
            }
            await $currentListView.fetchPageRecords();
            if(selectedResourceType === ResourceType.folder){
                $spaceChildren.refresh(space_name, subpath, true);
            }
            isOpen = false;
            showToast(Level.info, "Entry created successfully.");
        } catch (e) {
            errorContent = e.response.data;
            tick().then(() => {
                scrollToElById("error-content");
            });
        } finally {
            isHandleCreateEntryLoading = false;
        }

        isHandleCreateEntryLoading = false;
    }

    let selectedWorkflow = $state(null);

    $effect(()=>{
        if(isOpen === false) {
            content = {
                json: {}
            };
            metaContent = {};
            contentType = "json";
            errorContent = null;
            selectedSchema = null;
            selectedWorkflow = null;
            selectedInputMode = InputMode.form;
        }
    });

    $effect(()=>{
       if(allowedResourceTypes.length === 1) {
           untrack(()=>{
               selectedResourceType = allowedResourceTypes[0].value;
           })
       }
    });
</script>

<Modal
    bodyClass="h-s75vh justify-center"
    bind:open={isOpen}
    size="lg"
>
    {#snippet header()}
        <h3>Create New Entry</h3>
    {/snippet}
    {#if errorModalMessage}
    <Alert color="red">
        <span class="font-medium">{errorModalMessage}</span>
    </Alert>
    {/if}
    <div>
        <Label>
            Resource Type
            <Select class="my-2" items={allowedResourceTypes} bind:value={selectedResourceType}
                    disabled={allowedResourceTypes.length === 1}
            />
        </Label>

        <MetaForm bind:formData={metaContent} bind:validateFn={validateMetaForm} isCreate={true}/>

        {#if selectedResourceType === ResourceType.user}
            <MetaUserForm bind:formData={metaContent} bind:validateFn={validateRTForm}/>
        {:else if selectedResourceType === ResourceType.role}
            <MetaRoleForm bind:formData={metaContent} bind:validateFn={validateRTForm} />
        {:else if selectedResourceType === ResourceType.permission}
            <MetaPermissionForm bind:formData={metaContent} bind:validateFn={validateRTForm} />
        {/if}

        <PayloadForm
            bind:selectedResourceType={selectedResourceType}
            bind:selectedSchema={selectedSchema}
            bind:selectedWorkflow={selectedWorkflow}
            bind:selectedInputMode={selectedInputMode}
            bind:contentType={contentType}
            bind:content={content}
            bind:errorContent={errorContent}
        />

        {#if errorContent}
            <div id="error-content" class="mt-3">
                <Prism code={errorContent} language={"json"} />
            </div>
        {/if}
    </div>

    {#snippet footer()}
        <div class="w-full flex flex-row justify-between">
            {#if ([ResourceType.schema, ...resourcesWithFormAndJson].includes(selectedResourceType) || subpath === "workflows") && 
                 (selectedResourceType !== ResourceType.content || contentType === "json")}
                <Button class="cursor-pointer text-green-700 hover:text-green-500 mx-1" outline
                        onclick={() => selectedInputMode = selectedInputMode === InputMode.form ? InputMode.json : InputMode.form}>
                    {#if selectedInputMode === InputMode.form}
                        <CodeOutline />
                    {:else }
                        <FileCodeOutline />
                    {/if}
                    {selectedInputMode === InputMode.form ? 'Json' : 'Form'} Mode
                </Button>
            {:else}
                <div></div>
            {/if}
            <div>
                {#if !isHandleCreateEntryLoading}
                    <Button class="cursor-pointer text-primary hover:text-primary mx-1" outline onclick={() => isOpen = false}>
                        Close
                    </Button>
                {/if}

                <Button class="cursor-pointer bg-primary mx-1" onclick={handleCreateEntry}>
                    {#if isHandleCreateEntryLoading}
                        <Spinner class="me-3" size="4" color="blue" />
                        Creating ...
                    {:else}
                        Create
                    {/if}
                </Button>
            </div>
        </div>
    {/snippet}
</Modal>
