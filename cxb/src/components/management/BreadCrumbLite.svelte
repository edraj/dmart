<script lang="ts">
    import {ResourceType} from "@edraj/tsdmart";
    import {goto} from "@roxi/routify";
    import {onMount} from "svelte";
    import {Breadcrumb, BreadcrumbItem} from "flowbite-svelte";
    import {ChevronDoubleRightOutline, CodeForkSolid} from "flowbite-svelte-icons";

    $goto

    let {
        space_name,
        subpath,
        shortname,
        resource_type,
        schema_name,
        payloadContentType,
    } : {
        space_name: string,
        subpath: string,
        shortname?: string,
        resource_type: ResourceType,
        schema_name?: string,
        payloadContentType?: string,
    } = $props();

    let items = $state([]);
    onMount(() => {
        const parts = subpath.split("/");
        items = parts.filter((item) => item !== "").map((part, index) => ({
            text: `/${part}`.replaceAll("//", "/"),
            action: () =>
                $goto("/management/content/[space_name]/[subpath]", {
                    space_name: space_name,
                    subpath: parts
                        .slice(0, index + 1)
                        .join("/")
                        .replaceAll("/", "-"),
                }),
        }));
    });
</script>

<Breadcrumb aria-label="Solid background breadcrumb example" class="px-5 py-3 dark:bg-gray-900">
    <BreadcrumbItem href={`/management/content/${space_name}`} home>
        {#snippet icon()}
            <CodeForkSolid size="md" class="text-gray-500" style="transform: rotate(180deg);" />
        {/snippet} {space_name}
    </BreadcrumbItem>

    {#each items as item (item.text)}
        <BreadcrumbItem onclick={item.action} class="cursor-pointer">
            {#snippet icon()}
                <ChevronDoubleRightOutline class=" dark:text-white" />
            {/snippet}
            {item.text.replace("/", "")}
        </BreadcrumbItem>
    {/each}

    {#if ![ResourceType.folder, ResourceType.space].includes(resource_type)}
        <BreadcrumbItem>
            <strong>{shortname} </strong>&nbsp;(&nbsp;{resource_type} {#if payloadContentType} {`| ${payloadContentType}`}{/if}{#if schema_name}:{schema_name}{/if}&nbsp;)
        </BreadcrumbItem>
    {/if}
</Breadcrumb>
