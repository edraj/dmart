<script lang="ts">
  import {
    ResourceType,
    ResponseEntry,
    get_payload,
    progress_ticket,
  } from "@/dmart";
  import {
      Form,
      FormGroup,
      Button,
      Label,
      Input,
  } from "sveltestrap";
  import { showToast, Level } from "@/utils/toast";


  export let entry: ResponseEntry;
  export let space_name: string;
  export let subpath: string;


  const userRoles = JSON.parse(localStorage.getItem("roles"));


  let ticket_status = null;
  let ticket_action = null;
  let resolution = null;
  let comment;
  async function handleTicketSubmit(e) {
    e.preventDefault();
    const response = await progress_ticket(
      space_name,
      subpath,
      entry.shortname,
      ticket_action,
      resolution,
      comment
    );

    if (response.status === "success") {
      showToast(Level.info);
      window.location.reload();
    } else {
      showToast(Level.warn, response.error.message);
    }
  }

  let ticketPayload = null;
  async function get_ticket_payload() {
      ticketPayload = await get_payload(ResourceType.content, space_name, "workflows", entry.workflow_shortname)
  }

  let ticketStates = [];
  $:{
      if (ticketPayload){
        ticketStates = ticketPayload.states.filter((e) => e.state === entry.state)[0]?.next;
     }
  }

  let ticketResolutions = [];
  $:{    
      if ((ticketStates??[]).length){
          ticketResolutions = ticketPayload.states.filter((e) => e.state === ticket_status)[0]?.resolutions ?? [];
      }
  }

  $: {
      ticket_action = ticketStates?.filter((e) => e.state === ticket_status)[0]?.action ?? null;
  }

  $: {
      if (ticket_status){
          resolution = null;
      }
  }

</script>

<Form class="px-5 mb-5" on:submit={handleTicketSubmit}>
  {#await get_ticket_payload() then _}
    <FormGroup>
      {#if ticketStates}
      <Label>State</Label>
      <!-- on:change={handleInputChange} -->
      <Input
        class="w-25"
        type="select"
        name="status"
        placeholder="Status..."
        bind:value={ticket_status}
      >
        <option value={null}>Select next state</option>
        {#each ticketStates as e}
          <option value={e.state} disabled={!e.roles.some((el) => userRoles.includes(el))}>{e.state}</option>
        {/each}
      </Input>
      {/if}
    </FormGroup>
    {#key ticket_status}
      {#if ticketResolutions.length !== 0}
        <FormGroup>
          <Label>Resolution</Label>
          <Input
            class="w-25"
            type="select"
            name="resolution"
            placeholder="Resolution..."
            bind:value={resolution}
          >
            <option value={null}>Select resolution</option>
            {#each ticketResolutions as resolution}
              <option value={resolution}>{resolution}</option>
            {/each}
          </Input>
        </FormGroup>
      {/if}
    {/key}
  {/await}
  <FormGroup>
    <Label>Comment</Label>
    <!-- on:change={handleInputChange} -->
    <Input
      class="w-25"
      type="text"
      name="comment"
      placeholder="Comment..."
      bind:value={comment}
    />
  </FormGroup>
  <Button type="submit">Save</Button>
</Form>