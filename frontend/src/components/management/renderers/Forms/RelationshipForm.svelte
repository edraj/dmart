<script>
    import {Card, CardBody, Form, FormGroup, Label, Input, Button, Icon} from 'sveltestrap';

    export let content = [];

    content = [
        {
            property_domain: "",
            type: "",
            space_name: "",
            subpath: "",
            shortname: ""
        }
    ];



    // Add a new item to the array
    const addNewItem = () => {
        content = [
            ...content,
            {
                property_domain: "",
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
      {#each content as item, index}
        <Card>
          <CardBody>
            <div class="form-item">
            <FormGroup>
              <div class="d-flex justify-content-between">
                <Label>Property Domain</Label>
                <Icon
                  class="mx-1"
                  name="trash-fill"
                  style={"font-size: 1.5rem;"}
                  onclick={() => removeItem(index)}
                />
              </div>
              <Input type="url" bind:value={item.property_domain} />
            </FormGroup>
            <FormGroup>
              <Label>Type</Label>
              <Input bind:value={item.type} />
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
      <Button color="primary" class="w-100" on:click={addNewItem}>Add Relation</Button>
    </Form>
</Card>
