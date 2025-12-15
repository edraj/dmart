<script lang="ts">
    import {Badge, Card, Input, Label} from 'flowbite-svelte';
    import {SearchOutline} from 'flowbite-svelte-icons';
    import {onMount} from 'svelte';
    import {Dmart, QueryType} from '@edraj/tsdmart';

    let {
        formData = $bindable(),
        validateFn = $bindable()
    } = $props();

    let availablePermissions = $state([]);
    let loading = $state(true);
    let filteredPermissions = $state([]);
    let searchTerm = $state('');
    let showDropdown = $state(false);
    let dropdownWrapperRef;

    formData = {
        ...formData,
        permissions: formData.permissions || []
    };

    async function getPermissions() {
        try {
            const response: any = await Dmart.query({
                space_name: 'management',
                subpath: '/permissions',
                type: QueryType.search,
                search: '',
                limit: 100,
            });
            if (response) {
                availablePermissions = response.records;
                updateFilteredPermissions();
            }
        } catch (error) {
            console.error('Failed to load permissions:', error);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        getPermissions()

        const handleClickOutside = (event) => {
            if (dropdownWrapperRef && !dropdownWrapperRef.contains(event.target)) {
                showDropdown = false;
            }
        };
        document.addEventListener('click', handleClickOutside);
        return () => {
            document.removeEventListener('click', handleClickOutside);
        };
    });

    function updateFilteredPermissions() {
        filteredPermissions = availablePermissions
            .filter(perm => perm.shortname.toLowerCase().includes(searchTerm.toLowerCase()))
            .map(perm => ({ key: perm.shortname, value: perm.shortname }));
    }


    function togglePermission(event, permission) {
        event.stopPropagation();
        const index = formData.permissions.indexOf(permission.value);
        if (index === -1) {
            formData.permissions = [...formData.permissions, permission.value];
        } else {
            formData.permissions = formData.permissions.filter(p => p !== permission.value);
        }
    }

    function removePermission(permission) {
        formData.permissions = formData.permissions.filter(p => p !== permission);
    }

    function validate() {
        return formData.permissions.length !== 0;
    }

    $effect(() => {
        validateFn = validate;
    });

    $effect(() => {
        if(searchTerm){
            updateFilteredPermissions();
        } else {
            filteredPermissions = availablePermissions.map(perm => ({ key: perm.shortname, value: perm.shortname }));
        }
    });
</script>

<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    <h2 class="text-2xl font-bold mb-4">Role Permissions</h2>

    <div class="mb-4">
        <Label class="mb-2">
            <span class="text-red-500 text-lg" style="vertical-align: center">*</span>
            Permissions
        </Label>

        {#if loading}
            <div role="status" class="max-w-sm animate-pulse">
                <div class="h-3 bg-gray-200 rounded-full dark:bg-gray-700 mx-2 my-2.5"></div>
            </div>
        {:else}
            <div bind:this={dropdownWrapperRef}>
                <div class="relative mb-2">
                    <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                        <SearchOutline class="w-4 h-4 text-gray-500" />
                    </div>
                    <Input
                            class="pl-10"
                            placeholder="Search permissions..."
                            bind:value={searchTerm}
                            onfocus={() => showDropdown = true}
                    />
                </div>

                <div class="flex space-x-2">
                    <!-- Custom search with suggestions dropdown -->
                    <div class="relative flex-grow">
                        {#if showDropdown && filteredPermissions.length > 0}
                            <div class="absolute w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-60 overflow-auto">
                                {#each filteredPermissions as permission}
                                    <div
                                            class="px-4 py-2 hover:bg-gray-100 cursor-pointer flex items-center justify-between"
                                            onclick={(e) => togglePermission(e, permission)}
                                    >
                                        <span>{permission.key}</span>
                                        {#if formData.permissions.includes(permission.value)}
                                            <Badge color="blue">Selected</Badge>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    </div>
                </div>
            </div>
        {/if}

        <!-- Added permissions display -->
        {#if formData.permissions.length > 0}
            <div class="mt-4">
                <Label class="mb-2">Added Permissions</Label>
                <div class="border rounded-lg p-4 bg-gray-50">
                    <div class="flex flex-wrap gap-2">
                        {#each formData.permissions as permission}
                            <div class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full flex items-center">
                                <span>{permission}</span>
                                <button
                                        class="ml-2 text-blue-600 hover:text-blue-800"
                                        onclick={() => removePermission(permission)}
                                        type="button">
                                    ×
                                </button>
                            </div>
                        {/each}
                    </div>
                </div>
            </div>
        {:else}
            <div class="mt-4 p-4 border border-dashed rounded-lg text-center text-gray-500">
                No permissions added
            </div>
        {/if}
    </div>
</Card>