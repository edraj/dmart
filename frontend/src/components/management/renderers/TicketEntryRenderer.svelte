<script lang="ts">
    import {
        get_payload,
        progress_ticket,
        request,
        RequestType,
        ResourceType,
        type ResponseEntry,
        retrieve_entry,
    } from "@/dmart";
    import {Button, Form, FormGroup, Input, Label,} from "sveltestrap";
    import {Level, showToast} from "@/utils/toast";


  export let entry: ResponseEntry;
  export let space_name: string;
  export let subpath: string;


  const userRoles = JSON.parse(localStorage.getItem("roles"));

  let ticketElement: any = null;
  let ticket_status = null;
  let ticket_action = null;
  let resolution = null;
  let comment;
  let to_shortname="";
  async function handleTicketSubmit(e) {
    e.preventDefault();
    if (ticket_action === null && to_shortname===""){
        showToast(Level.info, "Nothing to be saved!");
        return;
    }

    if (to_shortname!=="") {
        const response = await request({
            space_name,
            request_type: RequestType.assign,
            records: [
                {
                    resource_type: ResourceType.ticket,
                    shortname: entry.shortname,
                    subpath,
                    attributes: {
                        is_active: true,
                        owner_shortname: to_shortname,
                        workflow_shortname: entry.workflow_shortname,
                        payload: {
                            content_type: entry.payload.content_type,
                            schema_shortname: entry.payload.schema_shortname
                        }
                    }
                }
            ]
        });
        if (response.status === "success") {
            showToast(Level.info);
            window.location.reload();
        }
        else {
            showToast(Level.warn, response.error.message);
        }
    }

    if (ticket_action === null){
        return;
    }

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
      ticketPayload = await retrieve_entry(ResourceType.content, space_name, "workflows", entry.workflow_shortname, true)
      console.log({ticketPayload})
  }

  let ticketStates = [];
  $:{
      if (ticketPayload){
        ticketStates = ticketPayload.states.filter((e) => e.state === entry.state)[0]?.next;
          console.log({state: entry.state})
          console.log({ticketStates})
     }
  }

  let ticketResolutions = [];
  $:{    
      if ((ticketStates??[]).length){
          ticketResolutions = ticketPayload.states.filter((e) => e.state === ticket_status)[0]?.resolutions ?? [];
          console.log({ticketResolutions})
      }
  }

  $: {
      ticket_action = ticketStates?.filter((e) => e.state === ticket_status)[0]?.action ?? null;
      console.log({ticket_action})
  }

  $: {
      if (ticket_status){
          resolution = null;
      }
  }
</script>

<Form class="d-flex flex-column justify-content-between w-50 p-5" on:submit={handleTicketSubmit}>
  <div class="d-flex flex-column px-5">
    {#await get_ticket_payload() then _}
      <FormGroup>
        {#if ticketStates}
          <Label>State</Label>
          <!-- on:change={handleInputChange} -->
          <Input
                  class=""
                  type="select"
                  name="status"
                  placeholder="Status..."
                  bind:value={ticket_status}
          >
            <option value={null}>Select next state</option>
            {#each ticketStates as e}
              <option bind:this={ticketElement} value={e.state} disabled={!e.roles.some((el) => userRoles.includes(el))}>{e.state} {(ticketElement && ticketElement.disabled) ? `(${e.roles})` : ""}</option>
            {/each}
          </Input>
        {/if}
      </FormGroup>
      {#key ticket_status}
        {#if ticketResolutions.length !== 0}
          <FormGroup>
            <Label>Resolution</Label>
            <Input
                    class=""
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
    {#if ticketStates.length}
      <FormGroup>
        <Label>Comment</Label>
        <!-- on:change={handleInputChange} -->
        <Input
          class=""
          type="text"
          name="comment"
          placeholder="Comment..."
          bind:value={comment}
        />
      </FormGroup>
    {/if}
    <FormGroup>
      <Label>Transfer</Label>
      <!-- on:change={handleInputChange} -->
      <Input
        class=""
        type="text"
        name="transfer"
        placeholder="Transfer to..."
        bind:value={to_shortname}
      />
    </FormGroup>
  </div>
  <Button color="primary" class="mx-auto justify-content-center" style="width: 75%" type="submit">Save</Button>
</Form>