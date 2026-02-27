<script lang="ts">
    import { _ } from "svelte-i18n";
    import { Level, showToast } from "@/utils/toast";
    import { Dmart } from "@edraj/tsdmart";
    import { Button, Card, Label, Fileupload, Alert } from "flowbite-svelte";
    import {
        InfoCircleSolid,
        FileImportOutline,
        ArrowLeftOutline,
    } from "flowbite-svelte-icons";
    import { goto } from "@roxi/routify";
    $goto;

    let zipFile: File | null = $state(null);
    let isUploading: boolean = $state(false);

    function handleFileChange(event: Event) {
        const target = event.target as HTMLInputElement;
        const files = target.files;

        if (files && files.length > 0) {
            const file = files[0];

            if (
                file.type === "application/zip" ||
                file.name.toLowerCase().endsWith(".zip")
            ) {
                zipFile = file;
            } else {
                showToast(Level.warn, $_("invalid_file_type"));
                target.value = "";
                zipFile = null;
            }
        }
    }

    async function handleUpload() {
        if (!zipFile) {
            showToast(Level.warn, $_("please_select_zip_file"));
            return;
        }

        isUploading = true;

        try {
            const formData = new FormData();
            formData.append("zip_file", zipFile);

            const response = await Dmart.axiosDmartInstance.post(
                "managed/import",
                formData,
                {
                    headers: {
                        ...Dmart.getHeaders(),
                        "Content-Type": "multipart/form-data",
                    },
                },
            );

            if (response.status === 200) {
                showToast(Level.info, $_("import_successful"));
                zipFile = null;
                const fileInput = document.getElementById(
                    "zip_file",
                ) as HTMLInputElement;
                if (fileInput) fileInput.value = "";
            } else {
                showToast(Level.warn, $_("import_failed"));
            }
        } catch (error: any) {
            console.error("Import error:", error);
            showToast(Level.warn, $_("import_failed"));
        } finally {
            isUploading = false;
        }
    }
</script>

<div class="container mx-auto p-8">
    <button
        class="flex items-center gap-2 text-gray-600 hover:text-primary-600 mb-6 transition-colors"
        onclick={() => $goto("/management/tools")}
    >
        <ArrowLeftOutline size="sm" />
        <span>Back to Tools</span>
    </button>

    <div class="flex items-center gap-3 mb-8">
        <div class="p-3 bg-primary-100 rounded-full">
            <FileImportOutline class="w-8 h-8 text-primary-600" />
        </div>
        <div>
            <h1 class="text-2xl font-bold">Import</h1>
            <p class="text-gray-500">Import entries based on zip file.</p>
        </div>
    </div>

    <div class="min-w-11/12">
        <Card class="min-w-full p-4">
            <div class="space-y-4">
                <Alert color="red" class="mb-4">
                    <InfoCircleSolid slot="icon" class="w-4 h-4" />
                    <span class="font-medium"><b>{$_("warning")}!</b></span>
                    {$_("import_warning_message")}
                </Alert>

                <div class="space-y-4">
                    <div>
                        <Label for="zip_file" class="mb-2"
                            >{$_("select_zip_file")}</Label
                        >
                        <Fileupload
                            id="zip_file"
                            accept=".zip,application/zip"
                            onchange={handleFileChange}
                            class="mb-2"
                        />
                        {#if zipFile}
                            <p class="text-sm text-gray-600 mt-1">
                                {$_("selected_file")}: {zipFile.name} ({(
                                    zipFile.size /
                                    1024 /
                                    1024
                                ).toFixed(2)} MB)
                            </p>
                        {/if}
                    </div>

                    <div class="flex justify-center">
                        <Button
                            onclick={handleUpload}
                            color="blue"
                            disabled={!zipFile || isUploading}
                            class="px-6 py-2"
                        >
                            {#if isUploading}
                                {$_("uploading")}...
                            {:else}
                                {$_("upload_and_import")}
                            {/if}
                        </Button>
                    </div>
                </div>
            </div>
        </Card>
    </div>
</div>
