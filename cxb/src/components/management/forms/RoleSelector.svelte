<script lang="ts">
    import { Badge, Input, Label } from "flowbite-svelte";
    import { SearchOutline } from "flowbite-svelte-icons";
    import { onMount } from "svelte";
    import { Dmart, QueryType } from "@edraj/tsdmart";

    let { selectedRoles = $bindable([]), label = "Roles" } = $props();

    let availableRoles = $state([]);
    let loading = $state(true);
    let filteredRoles = $state([]);
    let searchTerm = $state("");
    let showDropdown = $state(false);
    let dropdownWrapperRef = $state<HTMLElement>();

    async function getRoles() {
        try {
            const response: any = await Dmart.query({
                space_name: "management",
                subpath: "/roles",
                type: QueryType.search,
                search: "",
                limit: 100,
            });
            if (response) {
                availableRoles = response.records;
                updateFilteredRoles();
            }
        } catch (error) {
            console.error("Failed to load roles:", error);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        getRoles();

        const handleClickOutside = (event) => {
            if (
                dropdownWrapperRef &&
                !dropdownWrapperRef.contains(event.target)
            ) {
                showDropdown = false;
            }
        };
        document.addEventListener("click", handleClickOutside);
        return () => {
            document.removeEventListener("click", handleClickOutside);
        };
    });

    function updateFilteredRoles() {
        filteredRoles = availableRoles
            .filter((role) =>
                role.shortname.toLowerCase().includes(searchTerm.toLowerCase()),
            )
            .map((role) => ({ key: role.shortname, value: role.shortname }));
    }

    function toggleRole(event, role) {
        event.stopPropagation();
        const index = selectedRoles.indexOf(role.value);
        if (index === -1) {
            selectedRoles = [...selectedRoles, role.value];
        } else {
            selectedRoles = selectedRoles.filter((r) => r !== role.value);
        }
    }

    function removeRole(role) {
        selectedRoles = selectedRoles.filter((r) => r !== role);
    }

    $effect(() => {
        if (searchTerm) {
            updateFilteredRoles();
        } else {
            filteredRoles = availableRoles.map((role) => ({
                key: role.shortname,
                value: role.shortname,
            }));
        }
    });
</script>

<div class="w-full">
    <Label class="mb-2">{label}</Label>

    {#if loading}
        <div role="status" class="max-w-sm animate-pulse">
            <div
                class="h-3 bg-gray-200 rounded-full dark:bg-gray-700 mx-2 my-2.5"
            ></div>
        </div>
    {:else}
        <div bind:this={dropdownWrapperRef}>
            <div class="relative mb-2">
                <div
                    class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none"
                >
                    <SearchOutline class="w-4 h-4 text-gray-500" />
                </div>
                <Input
                    class="pl-10"
                    placeholder="Search roles..."
                    bind:value={searchTerm}
                    onfocus={() => (showDropdown = true)}
                />
            </div>

            <div class="relative">
                {#if showDropdown && filteredRoles.length > 0}
                    <div
                        class="absolute w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-60 overflow-auto"
                    >
                        {#each filteredRoles as role}
                            <button
                                type="button"
                                class="w-full px-4 py-2 hover:bg-gray-100 cursor-pointer flex items-center justify-between text-left"
                                onclick={(e) => toggleRole(e, role)}
                            >
                                <span>{role.key}</span>
                                {#if selectedRoles.includes(role.value)}
                                    <Badge color="blue">Selected</Badge>
                                {/if}
                            </button>
                        {/each}
                    </div>
                {/if}
            </div>
        </div>
    {/if}

    {#if selectedRoles.length > 0}
        <div class="mt-4">
            <div class="flex flex-wrap gap-2">
                {#each selectedRoles as role}
                    <div
                        class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full flex items-center"
                    >
                        <span>{role}</span>
                        <button
                            class="ml-2 text-blue-600 hover:text-blue-800"
                            onclick={() => removeRole(role)}
                            type="button"
                        >
                            ×
                        </button>
                    </div>
                {/each}
            </div>
        </div>
    {/if}
</div>
