<script lang="ts">
    import {Modal} from "flowbite-svelte";
    import Media from "@/components/management/renderers/Media.svelte";
    import {Dmart, ResourceType} from "@edraj/tsdmart";
    import {getFileExtension} from "@/utils/getFileExtension";

    let {
        space_name, subpath, parent_resource_type, parent_shortname,
        openViewContentModal = $bindable(), selectedAttachment
    }: {
        space_name: string, subpath: string, parent_resource_type: string, parent_shortname: string,
        openViewContentModal: boolean, selectedAttachment: any
    } = $props();

    function getModalClass(contentType) {
        if (!contentType) return "w-auto";
        if (contentType.includes("image")) return "max-w-screen-xl";
        if (contentType.includes("video")) return "max-w-screen-lg";
        if (contentType.includes("pdf")) return "max-w-4xl";
        if (contentType === "markdown") return "max-w-screen-md";
        return "w-auto"; // Default
    }

    let modalClass = $derived(getModalClass(selectedAttachment?.attributes?.payload?.content_type));
    let isPdf = $derived(selectedAttachment?.attributes?.payload?.content_type?.includes("pdf") || false);
</script>

<Modal
        class={modalClass}
        bodyClass={isPdf ? "p-0 h-auto" : "p-0 overflow-auto"}
        bind:open={openViewContentModal}
        autoclose={false}
        placement="center"
>
    <div class="modal-header flex justify-between items-center p-3 border-b">
        <h5 class="modal-title text-lg font-semibold">
            {selectedAttachment?.attributes?.displayname?.en || selectedAttachment?.shortname || "Attachment Content"}
        </h5>
    </div>

    {#if selectedAttachment}
        <div class={isPdf ? "pdf-container" : "media-container"}>
            <Media
                    resource_type={ResourceType[selectedAttachment.resource_type]}
                    attributes={selectedAttachment.attributes}
                    displayname={selectedAttachment.shortname}
                    url={Dmart.getAttachmentUrl({
                        resource_type: selectedAttachment.resource_type,
                        space_name: space_name,
                        subpath: subpath,
                        parent_shortname: (parent_resource_type === ResourceType.folder ? '' : parent_shortname),
                        shortname: selectedAttachment.shortname,
                        ext: getFileExtension(selectedAttachment.attributes?.payload?.body)
                    }
                )}
            />
        </div>
    {/if}
</Modal>

<style>
    .media-container {
        min-height: 200px;
        width: 100%;
        display: flex;
        justify-content: center;
        padding: 1rem;
        overflow: auto;
        max-height: 80vh;
    }

    .pdf-container {
        width: 100%;
        display: flex;
        justify-content: center;
        padding: 0;
        height: calc(80vh);
    }

    /* Content-specific styling */
    :global(.modal-image-content img) {
        max-height: 80vh;
        max-width: 100%;
        object-fit: contain;
    }

    :global(object[type="application/pdf"]) {
        width: 100%;
        height: 80vh !important;
    }
</style>