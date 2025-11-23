<script lang="ts">
    import {Alert, Button, Card, Input, Label, Select, TextPlaceholder} from "flowbite-svelte";
    import {Dmart, ResourceType} from "@edraj/tsdmart";
    import {Level, showToast} from "@/utils/toast";

    let {
        space_name,
        subpath,
        shortname,
        meta,
        formData = $bindable(),
    } = $props();

    const userRoles = JSON.parse(localStorage.getItem("roles"));

    let ticketElement = $state(null);
    let ticket_status = $state(null);
    let ticket_action = $state(null);
    let resolution = $state(null);
    let comment = $state("");
    // let to_shortname = $state("");

    let ticketPayload = $state(null);
    let ticketStates = $state([]);
    let ticketResolutions = $state([]);


    async function get_ticket_payload() {
        ticketPayload = await Dmart.retrieveEntry(
            {resource_type: ResourceType.content, space_name, subpath: "workflows", shortname: meta.workflow_shortname, retrieve_json_payload: true,retrieve_attachments:false,validate_schema:true}
        );
        ticketPayload = ticketPayload.payload.body;

        if (ticketPayload) {
            ticketStates = ticketPayload.states.filter((e) => e.state === meta.state)[0]?.next || [];

            if ((ticketStates || []).length) {
                ticketResolutions = ticketPayload.states.filter((e) => e.state === ticket_status)[0]?.resolutions || [];
            }
        }
    }

    $effect(() => {
        ticket_action = ticketStates?.filter((e) => e.state === ticket_status)[0]?.action || null;
    });

    $effect(() => {
        if ((ticketStates || []).length) {
            ticketResolutions = ticketPayload.states.filter((e) => e.state === ticket_status)[0]?.resolutions || [];
        }
    });

    $effect(() => {
        if (resolution) {
            formData.resolution = resolution;
        }
        if (ticket_action) {
            formData.action = ticket_action;
        }
        if (comment) {
            formData.comment = comment;
        }
    });

    /**
     * Progresses a ticket with the given data
     */
    async function progressTicket(e): Promise<{ success: boolean; errorMessage?: string }> {
        e.preventDefault();
        try {
            await Dmart.progressTicket({
                space_name,
                subpath,
                shortname,
                action: ticket_action,
                resolution,
                comment,
            });
            showToast(Level.info, `Ticket has been updated successfully!`);
            return { success: true };
        } catch (error: any) {
            showToast(Level.warn, `Failed to update the ticket!`);
            return { success: false, errorMessage: error.message };
        }
    }
</script>

<Card class="p-4 max-w-4xl mx-auto my-2">
    <h1 class="text-2xl font-bold mb-4">Ticket Form</h1>

    {#if meta.is_open}
        <form class="flex flex-col space-y-4" onsubmit={progressTicket}>
            {#await get_ticket_payload()}
                <TextPlaceholder class="m-5" size="lg" style="width: 100%"/>
                <TextPlaceholder class="m-5" size="lg" style="width: 100%"/>
            {:then _}
                {#if ticketStates.length}
                    <div class="mb-4">
                        <Label for="status" class="block mb-2">State</Label>
                        <Select id="status" bind:value={ticket_status}>
                            <option value={null}>Select an action</option>
                            {#each ticketStates as e}
                                <option
                                    value={e.state}
                                    disabled={!e.roles.some((el) => userRoles.includes(el))}
                                >
                                    {e.state} {e.roles && !e.roles.some((el) => userRoles.includes(el)) ? `(${e.roles})` : ""}
                                </option>
                            {/each}
                        </Select>
                    </div>
                {/if}

                {#key ticket_status}
                    {#if ticketResolutions.length !== 0}
                        <div class="mb-4">
                            <Label for="resolution" class="block mb-2">Resolution</Label>
                            <Select id="resolution" bind:value={resolution}>
                                <option value={null}>Select resolution</option>
                                {#each ticketResolutions as res}
                                    {#if typeof(res) === "string"}
                                        <option value={res}>{res}</option>
                                    {:else}
                                        <option value={res.key}>{res?.en}</option>
                                    {/if}
                                {/each}
                            </Select>
                        </div>
                    {/if}
                {/key}

                {#if ticket_status && !!ticketPayload.states.filter((e) => e.state === ticket_status)[0]?.next === false}
                    <div class="mb-4">
                        <Label for="comment" class="block mb-2">Comment</Label>
                        <Input id="comment" type="text" placeholder="Comment..." bind:value={comment} />
                    </div>
                {/if}

                <div class="mb-4 justify-end flex">
                    <Button type="submit" class="bg-primary text-white hover:bg-primary-700">
                        Submit
                    </Button>
                </div>

    <!--            <div class="mb-4">-->
    <!--                <Label for="transfer" class="block mb-2">Transfer</Label>-->
    <!--                <Input id="transfer" type="text" placeholder="Transfer to..." bind:value={to_shortname} />-->
    <!--            </div>-->
            {/await}
        </form>
    {:else}
        <Alert color="blue" class="mb-4 text-lg text-center">
            This ticket is closed. You cannot perform any actions on it.
        </Alert>
    {/if}
</Card>
