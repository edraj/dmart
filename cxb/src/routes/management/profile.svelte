<script lang="ts">
    import {Dmart} from "@edraj/tsdmart";
    import {Avatar, Badge, Card, Heading, Hr, Li, List, P} from "flowbite-svelte";
    import {getAvatar} from "@/lib/dmart_services";


    function getDisplayName(displayname) {
        if (!displayname) return "";
        return displayname.ar || displayname.en || "";
    }
    async function getProfile(){
        const profile: any = await Dmart.getProfile()
        return profile.records[0];
    }
</script>

{#await getProfile()}
    <div class="flex justify-center items-center h-64">
        <div class="text-center">
            <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto"></div>
            <p class="mt-3">Loading profile...</p>
        </div>
    </div>
{:then profile}
    <div class="flex min-w-full p-4">
        <Card class="bg-white shadow-lg rounded-lg p-6 min-w-full">
            <!-- Header with Avatar and basic info -->
            <div class="flex flex-col sm:flex-row items-center gap-5 mb-6">
                {#await getAvatar(profile.shortname)}
                    <Avatar
                        size="xl"
                        class="w-24 h-24 rounded"
                    >
                        {profile.shortname?.charAt(0).toUpperCase() || "U"}
                    </Avatar>
                {:then url}
                    <Avatar
                        size="xl"
                        class="w-24 h-24 rounded"
                        src={url}
                    >
                        {profile.shortname?.charAt(0).toUpperCase() || "U"}
                    </Avatar>
                {/await}


                <div class="flex flex-col items-center sm:items-start">
                    <div class="flex flex-row">
                        <Heading tag="h3" class="mb-1">{profile.attributes?.displayname?.en || 'N/A'}</Heading>
                        <Heading tag="h2" class="mb-1">•</Heading>
                        <Heading tag="h3" class="mb-1">{profile.attributes?.displayname?.ar || 'N/A'}</Heading>
                    </div>
                    <P class="text-gray-500 mb-2">@{profile.shortname}</P>

                    <div class="flex flex-wrap gap-2 mt-2">
                        {#each profile.attributes.roles || [] as role}
                            <Badge color="blue">{role}</Badge>
                        {/each}
                    </div>
                </div>
            </div>

            <Hr class="my-4" />

            <!-- Contact Information -->
            <div class="mb-6">
                <Heading tag="h3" class="text-xl font-semibold mb-3">Contact Information</Heading>

                <List class="space-y-3">
                    {#if profile.attributes.email}
                        <Li class="flex items-center">
                        <span class="mr-2">
                            <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                            </svg>
                        </span>
                            <span class="flex-1">{profile.attributes.email}</span>
                            {#if profile.attributes.is_email_verified}
                                <Badge color="green">Verified</Badge>
                            {:else}
                                <Badge color="yellow">Not Verified</Badge>
                            {/if}
                        </Li>
                    {/if}

                    {#if profile.attributes.msisdn}
                        <Li class="flex items-center">
                        <span class="mr-2">
                            <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                            </svg>
                        </span>
                            <span class="flex-1">{profile.attributes.msisdn}</span>
                            {#if profile.attributes.is_msisdn_verified}
                                <Badge color="green">Verified</Badge>
                            {:else}
                                <Badge color="yellow">Not Verified</Badge>
                            {/if}
                        </Li>
                    {/if}
                </List>
            </div>

            <Hr class="my-4" />

            <div class="mb-6">
                <Heading tag="h3" class="text-xl font-semibold mb-3">Account Details</Heading>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <P size="sm" color="font-semibold text-gray-500">User Type</P>
                        <P>{profile.attributes.type}</P>
                    </div>

                    <div>
                        <P size="sm" color="font-semibold text-gray-500">Language</P>
                        <P>{profile.attributes.language}</P>
                    </div>

                    {#if profile.attributes.force_password_change}
                        <div class="col-span-2">
                            <Badge color="red">Password change required</Badge>
                        </div>
                    {/if}
                </div>
            </div>

            <!-- Groups Section (if any) -->
            {#if profile.attributes.groups && profile.attributes.groups.length > 0}
                <Hr class="my-4" />

                <div>
                    <Heading tag="h3" class="text-xl font-semibold mb-3">Groups</Heading>
                    <div class="flex flex-wrap gap-2">
                        {#each profile.attributes.groups as group}
                            <Badge color="gray">{group}</Badge>
                        {/each}
                    </div>
                </div>
            {/if}
        </Card>
    </div>
{/await}
