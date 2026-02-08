<script lang="ts">
    import {
        Accordion,
        AccordionItem,
        Badge,
        Card,
        Checkbox,
        Helper,
        Input,
        Label,
        Select,
        Textarea
    } from 'flowbite-svelte';
    import {SearchOutline} from 'flowbite-svelte-icons';
    import {onMount} from 'svelte';
    import {Dmart, QueryType} from '@edraj/tsdmart';

    let {
        formData = $bindable(),
        validateFn = $bindable()
    } = $props();

    let form;

    let availableRoles = $state([]);
    let loadingRoles = $state(true);
    let filteredRoles = $state([]);
    let rolesSearchTerm = $state('');
    let showRolesDropdown = $state(false);
    let rolesDropdownRef;

    let availableGroups = $state([]);
    let loadingGroups = $state(true);
    let filteredGroups = $state([]);
    let groupsSearchTerm = $state('');
    let showGroupsDropdown = $state(false);
    let groupsDropdownRef = $state(null);

    formData = {
        ...formData,
        email: formData.email || null,
        password: formData.password || null,
        old_password: formData.old_password || null,
        msisdn: formData.msisdn || null,
        is_email_verified: formData.is_email_verified || false,
        is_msisdn_verified: formData.is_msisdn_verified || false,
        force_password_change: formData.force_password_change || false,
        type: formData.type || 'mobile',
        language: formData.language || null,
        roles: formData.roles || [],
        groups: formData.groups || [],
        firebase_token: formData.firebase_token || null,
        google_id: formData.google_id || null,
        facebook_id: formData.facebook_id || null,
        social_avatar_url: formData.social_avatar_url || null
    }

    const userTypeOptions = ["bot", "mobile", "web", "admin", "api"]
        .map(type => ({ name: type.charAt(0).toUpperCase() + type.slice(1), value: type }));

    async function getRoles() {
        try {
            const rolesResponse: any = await Dmart.query({
                space_name: 'management',
                subpath: '/roles',
                type: QueryType.search,
                search: '',
                limit: 100,
            });
            if (rolesResponse) {
                availableRoles = rolesResponse.records;
                updateFilteredRoles();
            }
        } catch (error) {
            console.error('Failed to load roles:', error);
        } finally {
            loadingRoles = false;
        }
    }

    async function getGroups() {
        try {
            const groupsResponse: any = await Dmart.query({
                space_name: 'management',
                subpath: '/groups',
                type: QueryType.search,
                search: '',
                limit: 100,
            });
            if (groupsResponse) {
                availableGroups = groupsResponse.records;
                updateFilteredGroups();
            }
        } catch (error) {
            console.error('Failed to load groups:', error);
        } finally {
            loadingGroups = false;
        }
    }

    onMount(() => {
        getRoles();
        getGroups();

        const handleClickOutside = (event) => {
            if (rolesDropdownRef && !rolesDropdownRef.contains(event.target)) {
                showRolesDropdown = false;
            }
            if (groupsDropdownRef && !groupsDropdownRef.contains(event.target)) {
                showGroupsDropdown = false;
            }
        };
        document.addEventListener('click', handleClickOutside);
        return () => {
            document.removeEventListener('click', handleClickOutside);
        };
    });

    function updateFilteredRoles() {
        filteredRoles = availableRoles
            .filter(role => role.shortname.toLowerCase().includes(rolesSearchTerm.toLowerCase()))
            .map(role => ({ key: role.shortname, value: role.shortname }));
    }

    function toggleRole(event, role) {
        event.stopPropagation();
        const index = formData.roles.indexOf(role.value);
        if (index === -1) {
            formData.roles = [...formData.roles, role.value];
        } else {
            formData.roles = formData.roles.filter(r => r !== role.value);
        }
    }

    function removeRole(role) {
        formData.roles = formData.roles.filter(r => r !== role);
    }

    function updateFilteredGroups() {
        filteredGroups = availableGroups
            .filter(group => group.shortname.toLowerCase().includes(groupsSearchTerm.toLowerCase()))
            .map(group => ({ key: group.shortname, value: group.shortname }));
    }

    function toggleGroup(event, group) {
        event.stopPropagation();
        const index = formData.groups.indexOf(group.value);
        if (index === -1) {
            formData.groups = [...formData.groups, group.value];
        } else {
            formData.groups = formData.groups.filter(g => g !== group.value);
        }
    }

    function removeGroup(group) {
        formData.groups = formData.groups.filter(g => g !== group);
    }

    function validate() {
        const isValid = form.checkValidity();
        isEmailValid = validateEmail(formData.email)

        if (!isValid || !isEmailValid) {
            form.reportValidity();
            return false;
        }
        return isValid;
    }

    $effect(() => {
        validateFn = validate;
    });

    $effect(() => {
        if(rolesSearchTerm){
            updateFilteredRoles();
        } else {
            filteredRoles = availableRoles.map(role => ({ key: role.shortname, value: role.shortname }));
        }
    });

    $effect(() => {
        if(groupsSearchTerm){
            updateFilteredGroups();
        } else {
            filteredGroups = availableGroups.map(group => ({ key: group.shortname, value: group.shortname }));
        }
    });


    let isEmailValid = $state(true);
    let emailTouched = $state(false);
    function validateEmail(email: string | null): boolean {
        if (!email) return true; // Empty is allowed as the field isn't required
        const emailRegex = /^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,6}$/;
        return emailRegex.test(email);
    }
    $effect(() => {
        if (emailTouched) {
            isEmailValid = validateEmail(formData.email);
        }
    });
</script>
<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    <h2 class="text-2xl font-bold mb-4">User Information</h2>

    <form bind:this={form} class="space-y-4">
        <div class="mb-4">
            <Label for="password" class="mb-2">
                <span class="text-red-500 text-lg" style="vertical-align: center">*</span>
                Old Password
            </Label>
            <Input required
                   id="password"
                   type="password"
                   placeholder="••••••••"
                   bind:value={formData.old_password}
                   minlength={8} />
        </div>
        <div class="mb-4">
            <Label for="password" class="mb-2">
                <span class="text-red-500 text-lg" style="vertical-align: center">*</span>
                New Password
            </Label>
            <Input required
                   id="old_password"
                   type="password"
                   placeholder="••••••••"
                   bind:value={formData.password}
                   minlength={8} />
            <Helper class="mt-1">Minimum 8 characters</Helper>
        </div>

        <div class="mb-4">
            <Label for="email" class="mb-2">Email</Label>
            <Input
                id="email"
                type="email"
                placeholder="user@example.com"
                pattern="[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{'{'}2,6{'}'}$"
                bind:value={formData.email}
                class={!isEmailValid ? "border-red-500" : ""}
                onblur={() => emailTouched = true}
            />
            {#if !isEmailValid && emailTouched}
                <Helper class="mt-1 text-red-600">Please enter a valid email address</Helper>
            {/if}
        </div>

        <div class="mb-4">
            <Label for="msisdn" class="mb-2">Mobile Number (MSISDN)</Label>
            <Input
                    id="msisdn"
                    placeholder="+964723456789 / 0712345678"
                    bind:value={formData.msisdn}
                    pattern="^\[1-9]\d$" />
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div class="flex items-center">
                <Checkbox id="force_password_change" bind:checked={formData.force_password_change} />
                <Label for="force_password_change" class="ml-2">Force Password Change</Label>
            </div>
            <div class="flex items-center">
                <Checkbox id="is_email_verified" bind:checked={formData.is_email_verified} />
                <Label for="is_email_verified" class="ml-2">Email Verified</Label>
            </div>
            <div class="flex items-center">
                <Checkbox id="is_msisdn_verified" bind:checked={formData.is_msisdn_verified} />
                <Label for="is_msisdn_verified" class="ml-2">Phone Number Verified</Label>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
                <Label for="user_type" class="mb-2">User Type</Label>
                <Select id="user_type" items={userTypeOptions} bind:value={formData.type} />
            </div>
            <div>
                <Label for="language" class="mb-2">Preferred Language</Label>
                <Input id="language" bind:value={formData.language} />
            </div>
        </div>

        <Accordion>
            <AccordionItem>
                {#snippet header()}Roles and Groups{/snippet}
                <div class="p-4 space-y-4">
                    <!-- Roles section -->
                    <div class="mb-4">
                        <Label class="mb-2">Roles</Label>

                        {#if loadingRoles}
                            <div role="status" class="max-w-sm animate-pulse">
                                <div class="h-3 bg-gray-200 rounded-full dark:bg-gray-700 mx-2 my-2.5"></div>
                            </div>
                        {:else}
                            <div bind:this={rolesDropdownRef}>
                                <div class="relative mb-2">
                                    <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                        <SearchOutline class="w-4 h-4 text-gray-500" />
                                    </div>
                                    <Input
                                            class="pl-10"
                                            placeholder="Search roles..."
                                            bind:value={rolesSearchTerm}
                                            onfocus={() => showRolesDropdown = true}
                                    />
                                </div>

                                <div class="flex space-x-2">
                                    <div class="relative flex-grow">
                                        {#if showRolesDropdown && filteredRoles.length > 0}
                                            <div class="absolute w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-60 overflow-auto">
                                                {#each filteredRoles as role}
                                                    <div
                                                            class="px-4 py-2 hover:bg-gray-100 cursor-pointer flex items-center justify-between"
                                                            onclick={(e) => toggleRole(e, role)}
                                                    >
                                                        <span>{role.key}</span>
                                                        {#if formData.roles.includes(role.value)}
                                                            <Badge color="blue">Selected</Badge>
                                                        {/if}
                                                    </div>
                                                {/each}
                                            </div>
                                        {/if}
                                    </div>
                                </div>
                            </div>

                            {#if formData.roles.length > 0}
                                <div class="mt-4">
                                    <Label class="mb-2">Added Roles</Label>
                                    <div class="border rounded-lg p-4 bg-gray-50">
                                        <div class="flex flex-wrap gap-2">
                                            {#each formData.roles as role}
                                                <div class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full flex items-center">
                                                    <span>{role}</span>
                                                    <button
                                                            class="ml-2 text-blue-600 hover:text-blue-800"
                                                            onclick={() => removeRole(role)}
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
                                    No roles added
                                </div>
                            {/if}
                        {/if}
                    </div>

                    <!-- Groups section - modified to match roles -->
                    <div class="mb-4">
                        <Label class="mb-2">Groups</Label>

                        {#if loadingGroups}
                            <div role="status" class="max-w-sm animate-pulse">
                                <div class="h-3 bg-gray-200 rounded-full dark:bg-gray-700 mx-2 my-2.5"></div>
                            </div>
                        {:else}
                            <div bind:this={groupsDropdownRef}>
                                <div class="relative mb-2">
                                    <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                        <SearchOutline class="w-4 h-4 text-gray-500" />
                                    </div>
                                    <Input
                                            class="pl-10"
                                            placeholder="Search groups..."
                                            bind:value={groupsSearchTerm}
                                            onfocus={() => showGroupsDropdown = true}
                                    />
                                </div>

                                <div class="flex space-x-2">
                                    <div class="relative flex-grow">
                                        {#if showGroupsDropdown && filteredGroups.length > 0}
                                            <div class="absolute w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-60 overflow-auto">
                                                {#each filteredGroups as group}
                                                    <div
                                                            class="px-4 py-2 hover:bg-gray-100 cursor-pointer flex items-center justify-between"
                                                            onclick={(e) => toggleGroup(e, group)}
                                                    >
                                                        <span>{group.key}</span>
                                                        {#if formData.groups.includes(group.value)}
                                                            <Badge color="blue">Selected</Badge>
                                                        {/if}
                                                    </div>
                                                {/each}
                                            </div>
                                        {/if}
                                    </div>
                                </div>
                            </div>

                            {#if formData.groups.length > 0}
                                <div class="mt-4">
                                    <Label class="mb-2">Added Groups</Label>
                                    <div class="border rounded-lg p-4 bg-gray-50">
                                        <div class="flex flex-wrap gap-2">
                                            {#each formData.groups as group}
                                                <div class="bg-gray-100 text-gray-800 px-3 py-1 rounded-full flex items-center">
                                                    <span>{group}</span>
                                                    <button
                                                            class="ml-2 text-blue-600 hover:text-blue-800"
                                                            onclick={() => removeGroup(group)}
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
                                    No groups added
                                </div>
                            {/if}
                        {/if}
                    </div>
                </div>
            </AccordionItem>

            <AccordionItem>
                {#snippet header()}Social and External IDs{/snippet}
                <div class="p-4 space-y-4">
                    <div class="mb-4">
                        <Label for="firebase_token" class="mb-2">Firebase Token</Label>
                        <Textarea id="firebase_token" placeholder="Firebase authentication token" bind:value={formData.firebase_token} rows={2} />
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <Label for="google_id" class="mb-2">Google ID</Label>
                            <Input id="google_id" bind:value={formData.google_id} />
                        </div>
                        <div>
                            <Label for="facebook_id" class="mb-2">Facebook ID</Label>
                            <Input id="facebook_id" bind:value={formData.facebook_id} />
                        </div>
                    </div>

                    <div>
                        <Label for="social_avatar_url" class="mb-2">Social Profile Image URL</Label>
                        <Input id="social_avatar_url" type="url" bind:value={formData.social_avatar_url} />
                    </div>
                </div>
            </AccordionItem>
        </Accordion>
    </form>
</Card>