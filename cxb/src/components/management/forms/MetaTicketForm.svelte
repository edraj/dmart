<script lang="ts">
    import {
        Alert,
        Button,
        Card,
        Input,
        Label,
        Select,
        TextPlaceholder,
    } from "flowbite-svelte";
    import { Dmart, ResourceType } from "@edraj/tsdmart";
    import { Level, showToast } from "@/utils/toast";
    import { untrack } from "svelte";

    let {
        space_name,
        subpath,
        shortname,
        meta,
        formData = $bindable(),
    } = $props();

    let userRoles: string[] = [];
    try {
        userRoles = JSON.parse(localStorage.getItem("roles") || "[]") || [];
    } catch {
        // Corrupted localStorage data
    }

    let ticket_status: string | null = $state(null);
    let ticket_action: string | null = $state(null);
    let resolution: string | null = $state(null);
    let comment = $state("");

    let ticketPayload: any = $state(null);
    let ticketStates: any[] = $state([]);
    let ticketResolutions: any[] = $state([]);
    let errorMessage = $state("");

    async function get_ticket_payload() {
        const response = await Dmart.retrieveEntry({
            resource_type: ResourceType.content,
            space_name,
            subpath: "workflows",
            shortname: meta.workflow_shortname,
            retrieve_json_payload: true,
            retrieve_attachments: false,
            validate_schema: true,
        });
        const payload = response?.payload?.body ?? null;
        ticketPayload = payload;
        if (payload) {
            ticketStates =
                payload.states.filter((e) => e.state === meta.state)[0]
                    ?.next || [];
        }
    }

    // Store the promise once at initialization to avoid re-calling on re-renders
    const ticketPromise = get_ticket_payload();

    $effect(() => {
        ticket_action =
            ticketStates?.filter((e) => e.state === ticket_status)[0]?.action ||
            null;
    });

    $effect(() => {
        if (ticketStates.length) {
            ticketResolutions =
                ticketPayload?.states?.filter((e: any) => e.state === ticket_status)[0]
                    ?.resolutions || [];
        }
    });

    $effect(() => {
        const _resolution = resolution;
        const _ticket_action = ticket_action;
        const _comment = comment;
        untrack(() => {
            if (_resolution) {
                formData.resolution = _resolution;
            }
            if (_ticket_action) {
                formData.action = _ticket_action;
            }
            if (_comment) {
                formData.comment = _comment;
            }
        });
    });

    /**
     * Progresses a ticket with the given data
     */
    async function progressTicket(
        e,
    ): Promise<{ success: boolean; errorMessage?: string }> {
        e.preventDefault();
        errorMessage = "";
        try {
            await Dmart.progressTicket({
                space_name,
                subpath,
                shortname,
                action: ticket_action ?? "",
                resolution: resolution ?? undefined,
                comment,
            });
            showToast(Level.info, `Ticket has been updated successfully!`);
            return { success: true };
        } catch (error: any) {
            showToast(Level.warn, `Failed to update the ticket!`);
            if(error?.response?.data?.error?.message){
                errorMessage = error?.response?.data?.error?.message
            } else {
                errorMessage = error.message;
            }

            return { success: false, errorMessage: error.message };
        }
    }
</script>

<Card class="p-4 max-w-4xl mx-auto my-2">
    <h1 class="text-2xl font-bold mb-4">Ticket Form</h1>

    {#if meta.is_open}
        <form class="flex flex-col space-y-4" onsubmit={progressTicket}>
            {#await ticketPromise}
                <TextPlaceholder class="m-5" size="lg" style="width: 100%" />
                <TextPlaceholder class="m-5" size="lg" style="width: 100%" />
            {:then _}
                {#if ticketStates.length}
                    <div class="mb-4">
                        <Label for="status" class="block mb-2">State</Label>
                        <Select id="status" bind:value={ticket_status}>
                            <option value={null}>Select an action</option>
                            {#each ticketStates as e}
                                <option
                                    value={e.state}
                                    disabled={!e.roles.some((el) =>
                                        userRoles.includes(el),
                                    )}
                                >
                                    {e.state}
                                    {e.roles &&
                                    !e.roles.some((el) =>
                                        userRoles.includes(el),
                                    )
                                        ? `(${e.roles})`
                                        : ""}
                                </option>
                            {/each}
                        </Select>
                    </div>
                {/if}

                {#key ticket_status}
                    {#if ticketResolutions.length !== 0}
                        <div class="mb-4">
                            <Label for="resolution" class="block mb-2"
                                >Resolution</Label
                            >
                            <Select id="resolution" bind:value={resolution}>
                                <option value={null}>Select resolution</option>
                                {#each ticketResolutions as res}
                                    {#if typeof res === "string"}
                                        <option value={res}>{res}</option>
                                    {:else}
                                        <option value={res.key}
                                            >{res?.en}</option
                                        >
                                    {/if}
                                {/each}
                            </Select>
                        </div>
                    {/if}
                {/key}

                {#if ticket_status && !!ticketPayload?.states?.filter((e: any) => e.state === ticket_status)[0]?.next === false}
                    <div class="mb-4">
                        <Label for="comment" class="block mb-2">Comment</Label>
                        <Input
                            id="comment"
                            type="text"
                            placeholder="Comment..."
                            bind:value={comment}
                        />
                    </div>
                {/if}

                <div class="mb-4 flex flex-col items-end">
                    <Button
                        type="submit"
                        class="bg-primary text-white hover:bg-primary-700"
                    >
                        Submit
                    </Button>
                    {#if errorMessage}
                        <div class="text-red-500 text-sm mt-2 font-medium">
                            {errorMessage}
                        </div>
                    {/if}
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
