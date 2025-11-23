<script lang="ts">
    import {
        Accordion,
        AccordionItem,
        Alert,
        Button,
        Card,
        Checkbox,
        Input,
        Label,
        Modal,
        Textarea
    } from 'flowbite-svelte';
    import {goto, params} from "@roxi/routify";
    import {Dmart, RequestType, ResourceType} from "@edraj/tsdmart";

    $goto

    let {
        isCreate,
        formData = $bindable(),
        validateFn = $bindable()
    } = $props();


    formData = {
        ...formData,
        shortname: formData.shortname || null,
        is_active: formData.is_active,
        slug: formData.slug || null,
        displayname: {
            en: formData.displayname?.en || null,
            ar: formData.displayname?.ar || null,
            ku: formData.displayname?.ku || null
        },
        description: {
            en: formData.description?.en || null,
            ar: formData.description?.ar || null,
            ku: formData.description?.ku || null
        },
    }
    if(formData.is_active === undefined || formData.is_active === null){
        formData.is_active = true;
    }

    let form;
    $effect(() => {
        validateFn = validate;
    });
    function validate() {
        const isValid = form.checkValidity();

        if (!isValid) {
            form.reportValidity();
        }

        return isValid;
    }

    let isShortnameUpdateOpen = $state(false);
    let newShortname = $state("");
    let isUpdatingShortname = $state(false);
    let shortnameUpdateError = $state(null);

    function handleShortnameModalUpdate() {
        newShortname = formData.shortname;
        isShortnameUpdateOpen = true;
    }

    async function updateShortname() {
        if (!newShortname || newShortname === formData.shortname) return;
        if (!newShortname.match(/^[a-zA-Z0-9_]+$/)) {
            shortnameUpdateError = "Shortname can only contain alphanumeric characters, underscores.";
            return;
        }


        isUpdatingShortname = true;

        try {
            const resourceType = $params.resource_type
                || ($params.subpath && ResourceType.folder)
                || ResourceType.space;
            let newSubpath = resourceType === ResourceType.folder
                ? ($params.subpath.split("-").slice(0, -1).join("/") || '/')
                : $params.subpath;

            if(resourceType === ResourceType.space){
                newSubpath = '/';
            }

            newSubpath = newSubpath.replaceAll("-", "/");

            const moveAttrb = {
                src_space_name: $params.space_name,
                src_subpath: newSubpath,
                src_shortname: formData.shortname,
                dest_space_name: resourceType === ResourceType.space ? newShortname : $params.space_name,
                dest_subpath: newSubpath,
                dest_shortname: newShortname,
            };

            await Dmart.request({
                space_name: $params.space_name,
                request_type: RequestType.move,
                records: [
                    {
                        resource_type: resourceType,
                        shortname: formData.shortname,
                        subpath: newSubpath,
                        attributes: moveAttrb,
                    },
                ],
            });

            let url = "/management/content";
            let gotoPayload: any = {
                space_name: $params.space_name,
            }
            if (resourceType === ResourceType.space) {
                window.location.href = newShortname;
            } else {
                if(resourceType === ResourceType.folder) {
                    url += '/[space_name]/[subpath]';
                    gotoPayload = {
                        ...gotoPayload,
                        subpath: `${newSubpath.replaceAll("-", "/")}-${newShortname}`,
                    }
                } else {
                    url += `/[space_name]/[subpath]/[shortname]/[resource_type]`;
                    gotoPayload = {
                        ...gotoPayload,
                        subpath: newSubpath.replaceAll("-", "/"),
                        shortname: newShortname,
                        resource_type: resourceType,
                    }
                }
            }
            $goto(`${url}`, gotoPayload);
        } catch (error) {
            shortnameUpdateError = error.response.data.error?.info[0]?.failed[0].error || error.response.data.error?.message || "An error occurred while updating the shortname.";
        } finally {
            isUpdatingShortname = false;
        }
    }

</script>

<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    <form bind:this={form} class="space-y-4">
        <h2 class="text-2xl font-bold mb-4">Meta Information</h2>
        <div class="mb-4">
            <Label for="shortname" class="mb-2">
                {#if isCreate}<span class="text-red-500 text-lg" style="vertical-align: center">*</span>{/if}
                Shortname
            </Label>
            <div class="flex">
                <Input required id="shortname"
                       class="rounded-l-none"
                       placeholder="Short name"
                       bind:value={formData.shortname}
                       disabled={!isCreate} />
                <Button color="alternative" class="rounded-l-none border-l-0"
                        onclick={() => isCreate ? (formData.shortname = "auto") : handleShortnameModalUpdate()}>
                    {isCreate ? 'Auto' : 'Update'}
                </Button>
            </div>
            {#if isCreate}
                <p class="text-xs text-gray-500 mt-1">
                    A shortname (use 'auto' for auto generated shortname)
                </p>
            {/if}
        </div>

        <div class="mb-4">
            <div class="flex items-center gap-2">
                <Checkbox id="is_active" bind:checked={formData.is_active} />
                <Label for="is_active" class="mb-0">Active</Label>
            </div>
            <p class="text-xs text-gray-500 mt-1">Whether this item is currently active</p>
        </div>

        <div class="mb-4">
            <Label for="slug" class="mb-2">Slug</Label>
            <Input id="slug" placeholder="url-friendly-name" bind:value={formData.slug} />
            <p class="text-xs text-gray-500 mt-1">A URL-friendly version of the short name</p>
        </div>

        <Accordion>
            <AccordionItem>
                <span slot="header" class="font-medium">Translations</span>
                {#snippet header()}Displayname and Description Translations{/snippet}
                <div class="p-4 space-y-4">
                    <div class="mb-4">
                        <Label class="mb-2">Display name</Label>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <Label class="text-sm">English</Label>
                                <Input bind:value={formData.displayname.en} />
                            </div>
                            <div>
                                <Label class="text-sm">Arabic</Label>
                                <Input bind:value={formData.displayname.ar} />
                            </div>
                            <div>
                                <Label class="text-sm">Kurdish</Label>
                                <Input bind:value={formData.displayname.ku} />
                            </div>
                        </div>
                    </div>

                    <div class="mb-4">
                        <Label class="mb-2">Description</Label>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <Label class="text-sm">English</Label>
                                <Textarea bind:value={formData.description.en} rows={3} />
                            </div>
                            <div>
                                <Label class="text-sm">Arabic</Label>
                                <Textarea bind:value={formData.description.ar} rows={3} />
                            </div>
                            <div>
                                <Label class="text-sm">Kurdish</Label>
                                <Textarea bind:value={formData.description.ku} rows={3} />
                            </div>
                        </div>
                    </div>
                </div>
            </AccordionItem>
        </Accordion>
    </form>
</Card>

<Modal bind:open={isShortnameUpdateOpen} size="md" title="Update Shortname">
    <div class="space-y-4">
        <p class="text-sm text-gray-500">
            Changing the shortname will move this resource to a new location. This may affect existing references to this item.
        </p>

        {#if shortnameUpdateError}
            <Alert color="red" class="mb-4">
                <span slot="icon" class="text-red-500">!</span>
                {shortnameUpdateError}
            </Alert>
        {/if}

        <div>
            <Label for="new-shortname">New Shortname</Label>
            <Input
                    id="new-shortname"
                    placeholder={formData.shortname}
                    bind:value={newShortname}
            />
        </div>

        <div class="flex justify-end gap-2 mt-4">
            <Button color="alternative" onclick={() => isShortnameUpdateOpen = false}>Cancel</Button>
            <Button
                    class="bg-primary"
                    disabled={!newShortname || newShortname === formData.shortname || isUpdatingShortname}
                    onclick={updateShortname}
            >
                {isUpdatingShortname ? "Updating..." : "Update Shortname"}
            </Button>
        </div>
    </div>
</Modal>