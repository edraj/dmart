<script lang="ts">
    import PermissionsExplorer from "@/components/management/renderers/PermissionsExplorer.svelte";
    import {Dmart} from "@edraj/tsdmart";
    import {ResourceType} from "@edraj/tsdmart/dmart.model";
    import {Card} from "flowbite-svelte";
    import {goto} from "@roxi/routify";

    $goto

    const {roles} = $props();

    function handleGoToRole(e, role) {
        e.preventDefault();
        $goto(
            `/management/content/[space_name]/[subpath]/[shortname]/[resource_type]`,
            {
                'space_name': 'management',
                'subpath': 'roles',
                'shortname': role,
                'resource_type': 'role'
            }
        );
    }
</script>

<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    {#each roles as role}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <p onclick={(e)=>handleGoToRole(e, role)} class="text-4xl cursor-pointer">{role}</p>
        {#await Dmart.retrieveEntry({
           resource_type: ResourceType.role,
           space_name: 'management',
           subpath: 'roles',
           shortname: role,
            retrieve_json_payload: true,
            retrieve_attachments: false,
            validate_schema: true
        }) then _role}
            <PermissionsExplorer permissions={_role.permissions} />
        {/await}
    {/each}
</Card>
