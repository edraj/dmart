<script>
    import SpaceSubpathItemsSidebar from "@/components/management/SpaceSubpathItemsSidebar.svelte";
    import { Drawer, Button, CloseButton } from "flowbite-svelte";
    import { BarsOutline } from "flowbite-svelte-icons";
    import { sineIn } from "svelte/easing";

    let hidden1 = $state(true);
    let transitionParams = {
        x: -320,
        duration: 200,
        easing: sineIn,
    };
</script>

<div class="flex h-full relative">
    <!-- Desktop Sidebar -->
    <div
        class="hidden md:block w-64 border-r border-gray-200 h-full flex-shrink-0 overflow-y-auto"
    >
        <SpaceSubpathItemsSidebar />
    </div>

    <!-- Mobile Drawer -->
    <Drawer
        {transitionParams}
        bind:hidden={hidden1}
        dismissable={false}
        id="sidebar-drawer"
        class="w-64 !max-w-none !h-[100dvh] !max-h-none !m-0 !rounded-none !p-0 md:hidden z-[100] bg-gray-50 dark:bg-gray-800 [&>div]:!p-0"
    >
        <div class="flex flex-col h-full w-full">
            <div
                class="flex items-center justify-between p-4 border-b border-gray-200 flex-shrink-0"
            >
                <h5
                    class="text-base font-semibold text-gray-500 uppercase dark:text-gray-400"
                >
                    Navigation
                </h5>
                <CloseButton
                    onclick={() => (hidden1 = true)}
                    class="dark:text-white"
                />
            </div>
            <div class="flex-1 overflow-y-auto">
                <SpaceSubpathItemsSidebar />
            </div>
        </div>
    </Drawer>

    <!-- Main Content -->
    <div class="flex-1 overflow-auto flex flex-col h-full w-full">
        <!-- Mobile Header (Hamburger Menu) -->
        <div
            class="md:hidden flex items-center p-4 border-b border-gray-200 bg-white z-10 sticky top-0"
        >
            <Button
                onclick={() => (hidden1 = false)}
                class="mr-4 p-2"
                outline
                color="alternative"
            >
                <BarsOutline class="w-5 h-5" />
            </Button>
            <span class="font-bold text-lg">Content Navigation</span>
        </div>

        <div class="flex-1 overflow-auto md:p-0 w-full pb-8 md:pb-8">
            <slot />
        </div>
    </div>
</div>
