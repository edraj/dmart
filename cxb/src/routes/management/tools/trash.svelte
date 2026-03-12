<script lang="ts">
    import ListView from "@/components/management/ListView.svelte";
    import { QueryType } from "@edraj/tsdmart";
    import { user } from "@/stores/user";
    
    let space_name = "personal";
    let subpath = `people/${$user.shortname}/trash`;
    
</script>

<div class="container mx-auto px-4 py-6 text-black dark:text-gray-100">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">Trash</h1>
    </div>

    <ListView 
        bind:space_name={space_name} 
        bind:subpath={subpath} 
        canDelete={true}
        exact_subpath={false}
        type={QueryType.search}
        sort_by="created_at"
        sort_order="ascending"
    />
</div>
