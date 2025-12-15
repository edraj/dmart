<script lang="ts">
    import {ListPlaceholder, SidebarItem} from "flowbite-svelte";
    import {ChevronDownOutline, ChevronRightOutline, FolderOutline} from "flowbite-svelte-icons";
    import SpacesSubpathItemsSidebar from "./SpacesSubpathItemsSidebar.svelte";
    import {activeRoute} from "@roxi/routify";
    import {untrack} from "svelte";
    import {spaceChildren} from "@/stores/global";

    let {
        spaceName,
        parentPath,
        item,
        depth = 0,
        expandedSpaces,
        loadChildren,
        toggleExpanded,
        isExpanded,
        getChildrenForSpace,
    } = $props();

    $effect(() => {
        if (`/-${$activeRoute.params.subpath}` === `${parentPath}-${item.shortname}`) {
            untrack(()=>{
                toggleExpanded(spaceName, getCurrentPath(), true);
            })
        }
    });

    function getCurrentPath() {
        let urll = `${parentPath}-${item.shortname}`.replace('/', '-').replace('--', '-');
        if (urll.startsWith('-')) {
            urll = urll.substring(1);
        }
        if (urll.endsWith('-')) {
            urll = urll.substring(0, urll.length - 1);
        }
        return `/${urll}`;
    }

    async function handleToggleExpanded() {
        await toggleExpanded(spaceName, getCurrentPath());
    }

    function getIsExpanded() {
        return isExpanded(spaceName, getCurrentPath());
    }

    export function preventAndHandleToggleExpanded(node: HTMLElement) {
        const handleEvent = (event: Event) => {
            event.preventDefault();
            event.stopPropagation();
            handleToggleExpanded()
        };

        node.addEventListener('click', handleEvent);

        return {
            destroy() {
                node.removeEventListener('click', handleEvent);
            }
        };
    }

    function isCurrentPath() {
        return `/${$activeRoute.params.subpath}` === getCurrentPath();
    }

    loadChildren(spaceName, getCurrentPath())
</script>

<SidebarItem
        label={item.attributes?.displayname?.en || item.shortname}
        href={`/management/content/${spaceName}${getCurrentPath()}`}
        class="flex-1 whitespace-nowrap {isCurrentPath() ? 'bg-gray-300 text-white' : ''}"
        style="margin-left: {depth * 20}px;">
    {#snippet icon()}
        <div class="flex items-center gap-2">
            <button class="p-1  rounded" use:preventAndHandleToggleExpanded>
                {#if getIsExpanded()}
                    <ChevronDownOutline size="sm" />
                {:else}
                    <ChevronRightOutline size="sm" />
                {/if}
            </button>

            <div>
                <FolderOutline
                    size="md"
                    class="text-gray-500"
                    style="transform: rotate(180deg); position: relative; z-index: 5;"
                />
            </div>
        </div>
    {/snippet}
</SidebarItem>

{#if getIsExpanded()}
    {#each $spaceChildren.data.get(`${spaceName}:${getCurrentPath()}`) as child (child.shortname)}
        <SpacesSubpathItemsSidebar
            {spaceName}
            parentPath={getCurrentPath()}
            item={child}
            depth={depth + 1}
            {expandedSpaces}
            {loadChildren}
            {toggleExpanded}
            {isExpanded}
            {getChildrenForSpace}
        />
    {/each}
{/if}
