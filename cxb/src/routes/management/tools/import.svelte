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
    let importEvents: Array<{
        timestamp: string;
        status: "success" | "error";
        filename: string;
        size: string;
        duration: string;
    }> = $state([]);

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

    function formatFileSize(bytes: number): string {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
        return (bytes / 1024 / 1024).toFixed(2) + " MB";
    }

    function formatDuration(ms: number): string {
        if (ms < 1000) return ms + "ms";
        const seconds = (ms / 1000).toFixed(1);
        return seconds + "s";
    }

    async function handleUpload() {
        if (!zipFile) {
            showToast(Level.warn, $_("please_select_zip_file"));
            return;
        }

        isUploading = true;
        const fileName = zipFile.name;
        const fileSize = formatFileSize(zipFile.size);
        const startTime = Date.now();

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
                importEvents = [
                    {
                        timestamp: new Date().toLocaleTimeString(),
                        status: "success",
                        filename: fileName,
                        size: fileSize,
                        duration: formatDuration(Date.now() - startTime),
                    },
                    ...importEvents,
                ];
                zipFile = null;
                const fileInput = document.getElementById(
                    "zip_file",
                ) as HTMLInputElement;
                if (fileInput) fileInput.value = "";
            } else {
                showToast(Level.warn, $_("import_failed"));
                importEvents = [
                    {
                        timestamp: new Date().toLocaleTimeString(),
                        status: "error",
                        filename: fileName,
                        size: fileSize,
                        duration: formatDuration(Date.now() - startTime),
                    },
                    ...importEvents,
                ];
            }
        } catch (error: any) {
            console.error("Import error:", error);
            const errorMsg =
                error?.response?.data?.error?.message ||
                error.message ||
                $_("import_failed");
            showToast(Level.warn, errorMsg);
            importEvents = [
                {
                    timestamp: new Date().toLocaleTimeString(),
                    status: "error",
                    filename: fileName,
                    size: fileSize,
                    duration: formatDuration(Date.now() - startTime),
                },
                ...importEvents,
            ];
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
                            disabled={isUploading}
                        />
                        {#if zipFile}
                            <p class="text-sm text-gray-600 mt-1">
                                {$_("selected_file")}: {zipFile.name} ({formatFileSize(
                                    zipFile.size,
                                )})
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

        {#if importEvents.length}
            <Card class="min-w-full p-4 mb-4">
                <h2 class="text-lg font-semibold mb-3">Import Log</h2>
                <div class="max-h-60 overflow-y-auto">
                    <table class="w-full text-sm text-left">
                        <thead
                                class="text-xs uppercase bg-gray-50 sticky top-0"
                        >
                        <tr>
                            <th class="px-3 py-2">Status</th>
                            <th class="px-3 py-2">File</th>
                            <th class="px-3 py-2">Size</th>
                            <th class="px-3 py-2">Duration</th>
                            <th class="px-3 py-2">Time</th>
                        </tr>
                        </thead>
                        <tbody>
                        {#each importEvents as event}
                            <tr
                                    class="border-b {event.status === 'success'
                                        ? 'bg-green-50 text-green-800'
                                        : 'bg-red-50 text-red-800'}"
                            >
                                <td class="px-3 py-2 font-semibold"
                                >{event.status === "success"
                                    ? "✓ Success"
                                    : "✗ Failed"}</td
                                >
                                <td class="px-3 py-2">{event.filename}</td>
                                <td class="px-3 py-2">{event.size}</td>
                                <td class="px-3 py-2">{event.duration}</td>
                                <td class="px-3 py-2 font-mono text-xs"
                                >{event.timestamp}</td
                                >
                            </tr>
                        {/each}
                        </tbody>
                    </table>
                </div>
            </Card>
        {/if}
    </div>
</div>
