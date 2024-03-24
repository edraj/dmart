<script lang="ts">
    import {
        Button,
        Form,
        FormGroup,
        Label,
        Input,
        Card,
        CardBody,
    } from 'sveltestrap';

    export let content: any = [];

    let newUserShortname = '';
    let newAllowedActions = '';

    const addACL = (e) => {
        e.preventDefault();
        content = [...content, { user_shortname: newUserShortname, allowed_actions: newAllowedActions }];
        newUserShortname = '';
        newAllowedActions = '';
    };

    const deleteUser = (index) => {
        content.splice(index, 1);
        content = [...content];
    };

    const updateUserInfo = (index, key, value) => {
        content[index][key] = value;
    };
</script>

{#each content as item, index}
  <Card key={index} class="mt-2">
    <CardBody>
      <FormGroup>
        <Label for="userShortname">User Shortname</Label>
        <Input bind:value={item.user_shortname} type="text" id="userShortname" placeholder="Enter user shortname" on:change={() => updateUserInfo(index, 'user_shortname', item.user_shortname)} />
      </FormGroup>
      <FormGroup>
        <Label for="allowedActions">Allowed Actions</Label>
        <select multiple bind:value={item.allowed_actions} class="form-control" id="allowedActions" on:change={() => updateUserInfo(index, 'allowed_actions', item.allowed_actions)}>
          <option value="query">Query</option>
          <option value="view">View</option>
          <option value="update">Update</option>
          <option value="create">Create</option>
          <option value="delete">Delete</option>
          <option value="attach">Attach</option>
          <option value="assign">Assign</option>
          <option value="move">Move</option>
          <option value="progress_ticket">Progress Ticket</option>
          <option value="lock">Lock</option>
          <option value="unlock">Unlock</option>
        </select>
      </FormGroup>
      <div class="d-flex justify-content-end">
        <Button class="btn-danger" on:click={() => deleteUser(index)}>Delete</Button>
      </div>
    </CardBody>
  </Card>
{/each}
<hr>
<Card class="mt-2 mb-5">
  <CardBody>
    <Form>
      <FormGroup>
        <Label for="userShortname">User Shortname</Label>
        <Input bind:value={newUserShortname} type="text" id="userShortname" placeholder="Enter user shortname" />
      </FormGroup>
      <FormGroup>
        <Label for="allowedActions">Allowed Actions</Label>
        <select multiple bind:value={newAllowedActions} class="form-control" id="allowedActions">
          <option value="query">Query</option>
          <option value="view">View</option>
          <option value="update">Update</option>
          <option value="create">Create</option>
          <option value="delete">Delete</option>
          <option value="attach">Attach</option>
          <option value="assign">Assign</option>
          <option value="move">Move</option>
          <option value="progress_ticket">Progress Ticket</option>
          <option value="lock">Lock</option>
          <option value="unlock">Unlock</option>
        </select>
      </FormGroup>
      <div class="d-flex justify-content-end">
        <Button class="btn-success" on:click={addACL}>Add ACL</Button>
      </div>
    </Form>
  </CardBody>
</Card>
