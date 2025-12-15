<script lang="ts">
    import {Card} from "flowbite-svelte";
    import {Dmart} from "@edraj/tsdmart";
    import {ResourceType} from "@edraj/tsdmart/dmart.model";
    import MetaPermissionForm from "@/components/management/forms/MetaPermissionForm.svelte";
    import {goto} from "@roxi/routify";

    $goto

    const {permissions} = $props();

    function handleGoToPermission(e, permission) {
        e.preventDefault();
        $goto(
            `/management/content/[space_name]/[subpath]/[shortname]/[resource_type]`,
            {
                'space_name': 'management',
                'subpath': 'permissions',
                'shortname': permission,
                'resource_type': 'permission'
            }
        );
    }
</script>

<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    {#each permissions as permission}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <p onclick={(e)=>handleGoToPermission(e, permission)} class="text-4xl cursor-pointer">{permission}</p>
        {#await Dmart.retrieveEntry({
            resource_type: ResourceType.permission,
            space_name: 'management',
            subpath: 'permissions',
            shortname: permission,
            retrieve_json_payload: true,
            retrieve_attachments: false,
            validate_schema: true
        }) then _role}
            <MetaPermissionForm formData={_role} readOnly={true}/>
        {/await}
    {/each}
</Card>