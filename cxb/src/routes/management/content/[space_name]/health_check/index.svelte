<script>
    import {spaces} from "@/stores/management/spaces";
    import {Card} from "flowbite-svelte";
    import {goto} from "@roxi/routify";

    $goto


    async function handleSelectedSpace(spaceShortname) {
        $goto(`/management/content/[space_name]/health_check/[space_name_health]`, {
            space_name: 'management',
            space_name_health: spaceShortname
        });
    }
</script>

<div class="container mx-auto px-12 py-6">
    <div class="flex justify-between items-center mb-1 px-1">
        <h1 class="text-2xl font-bold mb-6">Select Space to list the events</h1>
    </div>
    <hr class="mb-6 border-gray-300" />
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 gap-4 w-full place-items-center">
        {#each $spaces as space}
            <Card class="relative w-full">

                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <div class="flex flex-col items-center text-center p-4"
                     style="cursor: pointer"
                     onclick={() => handleSelectedSpace(space.shortname)}>
                    <span class="inline-block px-3 py-1 mb-3 border border-gray-300 rounded-md text-sm font-medium">
                        {space.shortname}
                    </span>

                    <h3 class="font-semibold text-lg">{space.attributes?.displayname?.en || space.shortname}</h3>

                    <p class="text-gray-600 mt-2 mb-4 line-clamp-3">
                        {space?.description?.en || ""}
                    </p>

                    <div class="text-xs text-gray-500 mt-auto">
                        Updated: {new Date(space?.attributes.updated_at).toLocaleDateString()}
                    </div>
                </div>
            </Card>
        {/each}
    </div>
</div>
