<script lang="ts">
    import {Card, CardBody, Form, FormGroup, Label, Input, Button, Icon, Alert} from 'sveltestrap';
    import {ResourceType} from "@/dmart";
    import {onMount} from "svelte";
    import {JSONEditor, Mode} from "svelte-jsoneditor";


    export let content = null;

    if (content === null) {
        content = [
            {
                type: "",
                space_name: "",
                subpath: "",
                shortname: "",
                attributes: {json: {}}
            }
        ];
    } else {
        content = (content ?? [])
            .map(c => c.related_to)
            .map(c => ({
                ...c, attributes: {json: c.attributes ?? {}}
            }))
    }


    // Add a new item to the array
    const addNewItem = () => {
        content = [
            ...content,
            {
                type: "",
                space_name: "",
                subpath: "",
                shortname: "",
                attributes: {json: {}}
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
        <Card style={item.error ? "border: solid red" : ""}>
          <CardBody>
            <div class="form-item">
              <FormGroup>
                {#if item.error}
                  <Alert color="danger">
                    {item.error}
                  </Alert>
                {/if}
                <div class="d-flex justify-content-between mb-2">
                  <Label>Resource Type</Label>
                  <Icon
                      class="mx-1"
                      name="trash-fill"
                      style={"font-size: 1.5rem;"}
                      onclick={() => removeItem(index)}
                  />
                </div>
                <Input type="select" bind:value={item.type}>
                  {#each Object.keys(ResourceType) as resourceType}
                    <option value={resourceType}>{resourceType}</option>
                  {/each}
                </Input>
              </FormGroup>
              <FormGroup>
                <Label>Space name</Label>
                <Input bind:value={item.space_name}/>
              </FormGroup>
              <FormGroup>
                <Label>Subpath</Label>
                <Input bind:value={item.subpath}/>
              </FormGroup>
              <FormGroup>
                <Label>Shortname</Label>
                <Input bind:value={item.shortname}/>
              </FormGroup>
              <FormGroup>
                <Label>attributes</Label>
                <JSONEditor
                        bind:content={item.attributes}
                        mode={Mode.text}
                />
              </FormGroup>
            </div>
          </CardBody>
        </Card>
      {/each}
    {/if}
    <Button color="primary" class="w-100 mt-2" onclick={addNewItem}>Add Relation</Button>
  </Form>
</Card>
