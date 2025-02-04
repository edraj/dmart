<script lang="ts">
    import {ListGroup, ListGroupItem} from "sveltestrap";

    export let subpath: any;
</script>

<ListGroupItem>
    {subpath.shortname}:
    {#if Array.isArray(subpath.subpaths)}
        <ListGroup flush>
            <ListGroup flush class="ms-3">
                {#each subpath.subpaths as nestedSubpaths}
                    {#each nestedSubpaths as nestedSubpath}
                        <svelte:self subpath={nestedSubpath} />
                    {/each}
                {/each}
            </ListGroup>
        </ListGroup>
    {:else}
        {subpath.subpaths} records.
    {/if}
</ListGroupItem>

<style>
    .ms-3 {
        margin-left: 1rem;
    }
</style>