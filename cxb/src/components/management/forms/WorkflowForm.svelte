<script lang="ts">
    import {Accordion, AccordionItem, Button, Card, Input, Label} from 'flowbite-svelte';
    import {PlusOutline, TrashBinOutline} from 'flowbite-svelte-icons';

    let {
        content = $bindable({}),
    } : {
        content: any,
    } = $props();

    content = {
        name: content.name || '',
        states: content.states || [],
        illustration: content.illustration || '',
        initial_state: content.initial_state || [],
    };

    function addState() {
        if(content.states === undefined) {
            content.states = [];
        }
        content.states = [...content.states, {
            name: '',
            state: '',
            next: [],
            resolutions: []
        }];
    }

    function removeState(event, index: number) {
        event.stopPropagation();
        content.states = content.states.filter((_, i) => i !== index);
    }

    function addNextTransition(stateIndex: number) {
        content.states[stateIndex].next = [
            ...content.states[stateIndex].next,
            { roles: [], state: '', action: '' }
        ];
    }

    function removeNextTransition(stateIndex: number, transitionIndex: number) {
        content.states[stateIndex].next = content.states[stateIndex].next.filter((_, i) => i !== transitionIndex);
    }

    function addResolution(stateIndex: number) {
        content.states[stateIndex].resolutions = [
            ...content.states[stateIndex].resolutions,
            { ar: '', en: '', ku: '', key: '' }
        ];
    }

    function removeResolution(stateIndex: number, resolutionIndex: number) {
        content.states[stateIndex].resolutions = content.states[stateIndex].resolutions.filter((_, i) => i !== resolutionIndex);
    }

    function addInitialState() {
        if(content.initial_state === undefined) {
            content.initial_state = [];
        }
        content.initial_state = [...content.initial_state, { name: '', roles: [] }];
    }

    function removeInitialState(index: number) {
        content.initial_state = content.initial_state.filter((_, i) => i !== index);
    }

    function addRole(item: any) {
        if(item.roles === undefined) {
            item.roles = [];
        }
        item.roles = [...(item.roles || []), ''];
    }

    function removeRole(item: any, roleIndex: number) {
        item.roles = item.roles.filter((_, i) => i !== roleIndex);
    }
</script>


<Card class="p-4 max-w-4xl mx-auto my-2">
    <h1 class="text-2xl font-bold mb-4">Workflow Form</h1>

    <div>
        <Label for="workflowName" class="mb-2">Workflow Name</Label>
        <Input id="workflowName" bind:value={content.name} placeholder="Enter workflow name" required />
    </div>

    <div>
        <Label for="illustration" class="mb-2">Illustration</Label>
        <Input id="illustration" bind:value={content.illustration} placeholder="Enter illustration name or path" />
    </div>

    <Card class="p-4 max-w-4xl mx-auto">
        <h3 class="text-xl font-semibold mb-2">Initial States</h3>
        <div class="space-y-4">
            {#each content.initial_state as initialState, index}
                <Card class="p-4 w-full">
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="text-lg font-medium">Initial State {index + 1}</h4>
                        <Button class="cursor-pointer text-red-500 hover:text-red-500" outline size="xs" onclick={() => removeInitialState(index)}>
                            <TrashBinOutline class="mr-1" />Remove
                        </Button>
                    </div>

                    <div class="space-y-3">
                        <div>
                            <Label for={`initialState${index}Name`}>Name</Label>
                            <Input id={`initialState${index}Name`} bind:value={initialState.name} placeholder="Initial state name" />
                        </div>

                        <div>
                            <Label>Roles</Label>
                            {#each initialState.roles as role, roleIndex}
                                <div class="flex items-center gap-2 mt-1">
                                    <Input bind:value={initialState.roles[roleIndex]} placeholder="Role name" />
                                    <Button class="cursor-pointer text-red-500 hover:text-red-500" outline size="xs" onclick={() => removeRole(initialState, roleIndex)}>
                                        <TrashBinOutline />
                                    </Button>
                                </div>
                            {/each}
                            <Button class="cursor-pointer mt-2 text-primary hover:text-primary" outline size="xs" onclick={() => addRole(initialState)}>
                                <PlusOutline class="mr-1" />Add Role
                            </Button>
                        </div>
                    </div>
                </Card>
            {/each}

            <Button onclick={addInitialState} class="cursor-pointer mt-2 text-primary hover:text-primary" outline>
                <PlusOutline class="mr-1" />Add Initial State
            </Button>
        </div>
    </Card>

    <Card class="p-4 max-w-4xl mx-auto">
        <h3 class="text-xl font-semibold mb-2">States</h3>
        <div class="space-y-4">
            {#each content.states as state, stateIndex}
                <Accordion>
                    <AccordionItem>
                        {#snippet header()}
                        <span class="flex justify-between items-center w-full">
                            <span>{state.name || `State ${stateIndex + 1}`}</span>
                            <Button class="cursor-pointer text-red-500 hover:text-red-500 " size="xs" onclick={(e) => removeState(e, stateIndex)}>
                                <TrashBinOutline />
                            </Button>
                        </span>
                        {/snippet}

                        <div class="p-2 space-y-4">
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <Label for={`state${stateIndex}Name`}>Name</Label>
                                    <Input id={`state${stateIndex}Name`} bind:value={state.name} placeholder="Human-readable state name" />
                                </div>
                                <div>
                                    <Label for={`state${stateIndex}Id`}>State ID</Label>
                                    <Input id={`state${stateIndex}Id`} bind:value={state.state} placeholder="Internal state identifier" />
                                </div>
                            </div>

                            <!-- Next Transitions -->
                            <div class="mt-4">
                                <Label class="text-lg">Next Transitions</Label>
                                <div class="space-y-3">
                                    {#each state.next as transition, transitionIndex}
                                        <Card class="p-3">
                                            <div class="flex justify-between items-center mb-2">
                                                <h5 class="font-medium">Transition {transitionIndex + 1}</h5>
                                                <Button class="cursor-pointer text-red-500 hover:text-red-500" size="xs" onclick={() => removeNextTransition(stateIndex, transitionIndex)}>
                                                    <TrashBinOutline />
                                                </Button>
                                            </div>

                                            <div class="grid grid-cols-2 gap-3">
                                                <div>
                                                    <Label>Next State</Label>
                                                    <Input bind:value={transition.state} placeholder="Next state identifier" />
                                                </div>
                                                <div>
                                                    <Label>Action</Label>
                                                    <Input bind:value={transition.action} placeholder="Action name" />
                                                </div>
                                            </div>

                                            <div class="mt-2">
                                                <Label>Roles</Label>
                                                {#each transition.roles as role, roleIndex}
                                                    <div class="flex items-center gap-2 mt-1">
                                                        <Input bind:value={transition.roles[roleIndex]} placeholder="Role name" />
                                                        <Button class="cursor-pointer text-red-500 hover:text-red-500" size="xs" onclick={() => removeRole(transition, roleIndex)}>
                                                            <TrashBinOutline />
                                                        </Button>
                                                    </div>
                                                {/each}
                                                <Button class="mt-2 cursor-pointer text-primary hover:text-primar" outline size="xs" onclick={() => addRole(transition)}>
                                                    <PlusOutline class="mr-1" />Add Role
                                                </Button>
                                            </div>
                                        </Card>
                                    {/each}
                                    <Button class="cursor-pointer text-primary hover:text-primar" outline size="sm" onclick={() => addNextTransition(stateIndex)}>
                                        <PlusOutline class="mr-1" />Add Transition
                                    </Button>
                                </div>
                            </div>

                            <!-- Resolutions -->
                            <div class="mt-4">
                                <Label class="text-lg">Resolutions</Label>
                                <div class="space-y-3">
                                    {#each state.resolutions as resolution, resolutionIndex}
                                        <Card class="p-3">
                                            <div class="flex justify-between items-center mb-2">
                                                <h5 class="font-medium">Resolution {resolutionIndex + 1}</h5>
                                                <Button class="cursor-pointer text-red-500 hover:text-red-500" size="xs" onclick={() => removeResolution(stateIndex, resolutionIndex)}>
                                                    <TrashBinOutline />
                                                </Button>
                                            </div>

                                            <div class="grid grid-cols-2 gap-3">
                                                <div>
                                                    <Label>Key</Label>
                                                    <Input bind:value={resolution.key} placeholder="Resolution key" />
                                                </div>
                                                <div>
                                                    <Label>English</Label>
                                                    <Input bind:value={resolution.en} placeholder="English translation" />
                                                </div>
                                                <div>
                                                    <Label>Arabic</Label>
                                                    <Input bind:value={resolution.ar} placeholder="Arabic translation" />
                                                </div>
                                                <div>
                                                    <Label>Kurdish</Label>
                                                    <Input bind:value={resolution.ku} placeholder="Kurdish translation" />
                                                </div>
                                            </div>
                                        </Card>
                                    {/each}
                                    <Button class="cursor-pointer text-primary hover:text-primar" outline size="sm" onclick={() => addResolution(stateIndex)}>
                                        <PlusOutline class="mr-1" />Add Resolution
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </AccordionItem>
                </Accordion>
            {/each}

            <Button outline onclick={addState} class="mt-2 cursor-pointer text-primary hover:text-primary">
                <PlusOutline class="mr-1" />Add State
            </Button>
        </div>
    </Card>
</Card>
