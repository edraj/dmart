<script>
    import {Card, CardBody, Form, FormGroup, Label, Input, Button, Icon} from 'sveltestrap';
    import {ResourceType} from "@/dmart";
    import {onMount} from "svelte";

    export let content = null;
    onMount(()=>{
        if (content === null) {
            content = [
                {
                    branch_name: "",
                    type: "",
                    space_name: "",
                    subpath: "",
                    shortname: ""
                }
            ];
        } else {
            content = (content ?? []).map(c=>c.related_to);
        }
    });


    // Add a new item to the array
    const addNewItem = () => {
        content = [
            ...content,
            {
                branch_name: "",
                type: "",
                space_name: "",
                subpath: "",
                shortname: ""
            }
        ];
    };

    // Remove an item by index
    const removeItem = (index) => {
        content = content.filter((_, i) => i !== index);
    };

    // Form Submit Handler
    const handleSubmit = (event) => {
        event.preventDefault();
    };
</script>

<Card>
    <Form on:submit={handleSubmit}>
      {#if content}
      {#each content as item, index}
        <Card>
          <CardBody>
            <div class="form-item">
            <FormGroup>
              <div class="d-flex justify-content-between">
                <Label>Branch name</Label>
                <Icon
                  class="mx-1"
                  name="trash-fill"
                  style={"font-size: 1.5rem;"}
                  onclick={() => removeItem(index)}
                />
              </div>
              <Input type="url" bind:value={item.branch_name} />
            </FormGroup>
            <FormGroup>
              <Label>Resource Type</Label>
              <Input type="select" bind:value={item.type}>
                {#each Object.keys(ResourceType) as resourceType}
                  <option value={resourceType}>{resourceType}</option>
                {/each}
              </Input>
            </FormGroup>
            <FormGroup>
              <Label>Space name</Label>
              <Input bind:value={item.space_name} />
            </FormGroup>
            <FormGroup>
              <Label>Subpath</Label>
              <Input bind:value={item.subpath} />
            </FormGroup>
            <FormGroup>
              <Label>Shortname</Label>
              <Input bind:value={item.shortname} />
            </FormGroup>
          </div>
          </CardBody>
        </Card>
      {/each}
      {/if}
      <Button color="primary" class="w-100" on:click={addNewItem}>Add Relation</Button>
    </Form>
</Card>
