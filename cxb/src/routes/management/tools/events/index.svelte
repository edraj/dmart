<script>
    import { spaces } from "@/stores/management/spaces";
    import { Card } from "flowbite-svelte";
    import {
        CalendarMonthOutline,
        ArrowLeftOutline,
    } from "flowbite-svelte-icons";
    import { goto } from "@roxi/routify";

    $goto;

    async function handleSelectedSpace(spaceShortname) {
        $goto(`/management/tools/events/[space_name]`, {
            space_name: spaceShortname,
        });
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
            <CalendarMonthOutline class="w-8 h-8 text-primary-600" />
        </div>
        <div>
            <h1 class="text-2xl font-bold">Events</h1>
            <p class="text-gray-500">
                Check all Dmart instance events. Select a space below to view.
            </p>
        </div>
    </div>
    <hr class="mb-6 border-gray-300" />
    <div
        class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 gap-4 w-full place-items-center"
    >
        {#each $spaces as space}
            <Card class="relative w-full">
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <div
                    class="flex flex-col items-center text-center p-4"
                    style="cursor: pointer"
                    onclick={() => handleSelectedSpace(space.shortname)}
                >
                    <span
                        class="inline-block px-3 py-1 mb-3 border border-gray-300 rounded-md text-sm font-medium"
                    >
                        {space.shortname}
                    </span>

                    <h3 class="font-semibold text-lg">
                        {space.attributes?.displayname?.en || space.shortname}
                    </h3>

                    <p class="text-gray-600 mt-2 mb-4 line-clamp-3">
                        {space?.description?.en || ""}
                    </p>

                    <div class="text-xs text-gray-500 mt-auto">
                        Updated: {new Date(
                            space?.attributes.updated_at,
                        ).toLocaleDateString()}
                    </div>
                </div>
            </Card>
        {/each}
    </div>
</div>
