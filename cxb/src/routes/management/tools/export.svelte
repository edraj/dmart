<script lang="ts">
    import { _ } from "svelte-i18n";
    import { onMount } from "svelte";
    import downloadFile from "@/utils/downloadFile";
    import { Level, showToast } from "@/utils/toast";
    import {
        Dmart,
        type QueryRequest,
        QueryType,
        ResourceType,
    } from "@edraj/tsdmart";
    import { getChildren } from "@/lib/dmart_services";
    import {
        Button,
        Card,
        Checkbox,
        Input,
        Label,
        Select,
    } from "flowbite-svelte";
    import {
        FilterOutline,
        FilterSolid,
        FileExportOutline,
        ArrowLeftOutline,
    } from "flowbite-svelte-icons";
    import Prism from "@/components/Prism.svelte";
    import { goto } from "@roxi/routify";
    $goto;
    import {
        addDateFilters,
        createBaseQuery,
    } from "@/utils/routes/queryHelpers";
    import { headers } from "@edraj/tsdmart/dmart.model";

    // Constants
    const DEFAULT_QUERY_LIMIT = 10;

    let spaces = $state([]);
    let space_name: string = $state("");
    // let queryType: QueryType = $state(null);
    let subpath: string = $state("/");
    // let resource_type: ResourceType = $state(null);
    // let resource_shortnames: string = $state("");
    // let search: string = $state("");
    // let from_date: string = $state("");
    // let to_date: string = $state("");
    // let offset: number = $state(0);
    // let limit: number = $state(DEFAULT_QUERY_LIMIT);
    // let retrieve_attachments: boolean = $state(false);
    // let retrieve_json_payload: boolean = $state(false);

    let response = $state(null);
    let isDisplayFilter = $state(false);
    let isExporting: boolean = $state(false);
    let exportEvents: Array<{
        timestamp: string;
        status: "success" | "error";
        filename: string;
        size: string;
        duration: string;
    }> = $state([]);

    let selectedSpacename = $state(null);
    let tempSubpaths = $state([]);
    let subpaths = $state([]);

    onMount(() => {
        async function setup() {
            spaces = (await Dmart.getSpaces()).records;
        }
        setup();
    });

    async function buildSubpaths(base: string, _subpaths: any) {
        for (const _subpath of _subpaths.records) {
            if (_subpath.resource_type === "folder") {
                const childSubpaths = await getChildren(
                    space_name,
                    _subpath.shortname,
                );
                await buildSubpaths(
                    `${base}/${_subpath.shortname}`,
                    childSubpaths,
                );
                tempSubpaths.push(`${base}/${_subpath.shortname}`);
            }
        }
    }

    async function handleResponse() {
        if (!space_name || !subpath) {
            return;
        }

        const query_request: QueryRequest = {
            type: QueryType.search,
            exact_subpath: false,
            ...createBaseQuery({
                space_name,
                subpath,
                search: "",
                offset: 0,
                limit: 1_000_000,
                retrieve_json_payload: true,
                retrieve_attachments: true,
            }),
        };

        response = await Dmart.query(query_request);
    }

    function formatFileSize(bytes: number): string {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
        return (bytes / 1024 / 1024).toFixed(2) + " MB";
    }

    function formatDuration(ms: number): string {
        if (ms < 1000) return ms + "ms";
        return (ms / 1000).toFixed(1) + "s";
    }

    async function handleDownload() {
        const body: any = {
            type: QueryType.search,
            exact_subpath: false,
            ...createBaseQuery({
                space_name,
                subpath,
                search: "",
                offset: 0,
                limit: 1_000_000,
                retrieve_json_payload: true,
                retrieve_attachments: true,
            }),
        };

        isExporting = true;
        const fileName = `${space_name}/${subpath}.zip`;
        const startTime = Date.now();

        try {
            const response = await Dmart.axiosDmartInstance.post(
                `managed/export`,
                body,
                { headers, responseType: "arraybuffer" },
            );

            // Check if response is successful based on status code
            if (response.status !== 200) {
                showToast(Level.warn);
                exportEvents = [
                    {
                        timestamp: new Date().toLocaleTimeString(),
                        status: "error",
                        filename: fileName,
                        size: "-",
                        duration: formatDuration(Date.now() - startTime),
                    },
                    ...exportEvents,
                ];
            } else {
                const fileSize = formatFileSize(response.data.byteLength);
                downloadFile(response.data, fileName, "application/zip");
                exportEvents = [
                    {
                        timestamp: new Date().toLocaleTimeString(),
                        status: "success",
                        filename: fileName,
                        size: fileSize,
                        duration: formatDuration(Date.now() - startTime),
                    },
                    ...exportEvents,
                ];
            }
        } catch (error: any) {
            showToast(Level.warn);
            exportEvents = [
                {
                    timestamp: new Date().toLocaleTimeString(),
                    status: "error",
                    filename: fileName,
                    size: "-",
                    duration: formatDuration(Date.now() - startTime),
                },
                ...exportEvents,
            ];
        } finally {
            isExporting = false;
        }
    }

    $effect(() => {
        if (space_name && selectedSpacename !== space_name) {
            (async () => {
                subpaths = [];
                tempSubpaths = [];
                const _subpaths = await getChildren(space_name, "/");

                await buildSubpaths("", _subpaths);

                subpaths = [...tempSubpaths.reverse()];
                selectedSpacename = `${space_name}`;
            })();
        }
    });
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
            <FileExportOutline class="w-8 h-8 text-primary-600" />
        </div>
        <div>
            <h1 class="text-2xl font-bold">Export</h1>
            <p class="text-gray-500">Export entries as zip file.</p>
        </div>
    </div>

    <div class="min-w-11/12">

        <Card class="min-w-full p-4">
            <div class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-12 gap-4 mb-4">
                    <div class="md:col-span-4">
                        <Label for="space_name" class="mb-2"
                            >{$_("space_name")}</Label
                        >
                        <Select
                            id="space_name"
                            bind:value={space_name}
                            disabled={isExporting}
                        >
                            {#each spaces as space}
                                <option value={space.shortname}
                                    >{space.shortname}</option
                                >
                            {/each}
                        </Select>
                    </div>
                    <div class="md:col-span-4">
                        <Label for="subpath" class="mb-2">{$_("subpath")}</Label
                        >
                        <Select
                            id="subpath"
                            bind:value={subpath}
                            disabled={isExporting}
                        >
                            <option value={"/"}>/</option>
                            {#each subpaths as path}
                                <option value={path}>{path}</option>
                            {/each}
                        </Select>
                    </div>
                </div>
                <div class="md:col-span-4 mx-auto flex items-end justify-end">
                    <Button
                        onclick={handleResponse}
                        color="blue"
                        disabled={isExporting}>{$_("submit")}</Button
                    >
                    <Button
                        class="mx-5"
                        color="blue"
                        outline
                        disabled={isExporting}
                        onclick={handleDownload}
                        >{isExporting
                            ? $_("uploading") + "..."
                            : $_("download_zip")}</Button
                    >
                </div>
            </div>
        </Card>

        {#if exportEvents.length}
            <Card class="min-w-full p-4 mb-4">
                <h2 class="text-lg font-semibold mb-3">Export Log</h2>
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
                        {#each exportEvents as event}
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

    {#if response === null}
        <p class="text-gray-500 text-center">No response yet.</p>
    {:else}
        <Prism bind:code={response} />
    {/if}
</div>
