<script>
    import {Button, FormGroup, Input, Label, Modal, ModalBody, ModalFooter} from "sveltestrap";
    import Prism from "@/components/Prism.svelte";

    let {
        openDownloadModal = $bindable(),
        startDateCSVDownload = $bindable(),
        endDateCSVDownload = $bindable(),
        limitCSVDownload = $bindable(),
        searchTextCSVDownload = $bindable(),
        errorContent = $bindable(),
        handleDownload
    } = $props();
</script>

<Modal isOpen={openDownloadModal} toggle={() => (openDownloadModal = false)} size="lg">
    <div class="modal-header">
        <h5 class="modal-title">Download Data</h5>
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <button type="button" onclick={() => (openDownloadModal = false)} class="btn-close" aria-label="Close">
        </button>
    </div>

    <ModalBody>
        <FormGroup>
            <Label for="startDate">Start Date</Label>
            <Input type="date" id="startDate" bind:value={startDateCSVDownload} />
        </FormGroup>
        <FormGroup>
            <Label for="endDate">End Date</Label>
            <Input type="date" id="endDate" bind:value={endDateCSVDownload} />
        </FormGroup>
        <FormGroup>
            <Label for="limit">Limit</Label>
            <Input type="number" id="limit" bind:value={limitCSVDownload} min="0"/>
        </FormGroup>
        <FormGroup>
            <Label for="searchText">Search Text</Label>
            <Input type="text" id="searchText" bind:value={searchTextCSVDownload} />
        </FormGroup>
        {#if errorContent}
            <h3 class="mt-3">Error:</h3>
            <Prism bind:code={errorContent} />
        {/if}
    </ModalBody>
    <ModalFooter>
        <Button color="secondary" onclick={() => (openDownloadModal = false)}>Cancel</Button>
        <Button color="primary" onclick={handleDownload}>Download</Button>
    </ModalFooter>
</Modal>