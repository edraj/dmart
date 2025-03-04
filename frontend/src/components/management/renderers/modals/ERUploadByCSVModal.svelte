<script>
    import {query, QueryType} from "@/dmart";
    import {Button, Input, Label, Modal, ModalBody, ModalFooter} from "sveltestrap";
    import Prism from "@/components/Prism.svelte";

    let {
        openUploadByCSVModal = $bindable(),
        allowedResourceTypes = $bindable(),
        space_name = $bindable(),
        new_resource_type = $bindable(),
        selectedSchema = $bindable(),
        payloadFiles = $bindable(),
        errorContent = $bindable(),
        handleUpload,
        setSchemaItems,
    } = $props();
</script>

<Modal
        isOpen={openUploadByCSVModal}
        toggle={()=>{openUploadByCSVModal=false}}
        size={"lg"}
>
    <ModalBody>
        <Label for="resource_type" class="mt-3">Resource type</Label>
        <Input
                id="resource_type"
                bind:value={new_resource_type}
                type="select"
        >
            {#each allowedResourceTypes as type}
                {#if type}
                    <option value={type}>{type}</option>
                {/if}
            {/each}
        </Input>

        <Label class="mt-3">Schema</Label>
        <Input bind:value={selectedSchema} type="select">
            <option value={null}>{"None"}</option>
            {#await query({
                space_name,
                type: QueryType.search,
                subpath: "/schema",
                search: "",
                retrieve_json_payload: true,
                limit: 99
            }) then schemas}
                {#each setSchemaItems(schemas) as schema}
                    <option value={schema}>{schema}</option>
                {/each}
            {/await}
        </Input>

        <Label class="mt-3">CSV File</Label>
        <Input bind:files={payloadFiles} type="file" accept=".csv" />

        <hr/>
        {#if errorContent}
            <h3 class="mt-3">Error:</h3>
            <Prism bind:code={errorContent}/>
        {/if}
    </ModalBody>

    <ModalFooter>
        <Button
                type="button"
                color="secondary"
                onclick={() => (openUploadByCSVModal = false)}
        >close</Button>
        <Button type="button" color="primary" onclick={handleUpload}>Upload</Button>
    </ModalFooter>
</Modal>