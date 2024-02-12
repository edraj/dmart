<script lang="ts">
    import { onMount } from "svelte";
    import { Col, Icon, Input, Row } from "sveltestrap";

    export let content: any = [];

    let inputs = [];

    onMount(() => {
        if (content.length) {
            inputs = content.map(c=>{
                return { value: c }
            }); 
        } else {
            inputs = [{ value: "" }]
        }
        
    });

    function addInput(e) {
        e.preventDefault();
        inputs = [...inputs, { value: "" }];
    }

    function removeInput(index) {
        inputs = inputs.filter((_, i) => i !== index);
    }

    $: {
        content = inputs.map((i) => i.value).filter((i) => i.length);
    }
</script>

{#each inputs as input, index}
<Row class="mb-2">
    <Col sm="10"><Input type="text" class="form-control" bind:value={input.value} placeholder="Permission name..." /></Col>
    <Col sm="2" class="align-self-center p-0">
        <Icon class="mx-1" name="trash-fill" onclick={() => removeInput(index)} style={"font-size: 1.5rem;"} />
        {#if index == inputs.length - 1}
            <Icon class="mx-1" name="plus-square-fill" onclick={addInput} style={"font-size: 1.5rem;"}/>
        {/if}
    </Col>
</Row>
{/each}
