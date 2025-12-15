<script>
    import SpaceSubpathItemsSidebar from "@/components/management/SpaceSubpathItemsSidebar.svelte";
</script>

<div class="flex h-full">
    <div class="w-64 border-r border-gray-200">
        <!--        <SpacesSidebar />-->
        <SpaceSubpathItemsSidebar />
    </div>

    <div class="flex-1 overflow-auto">
        <slot />
    </div>
</div>