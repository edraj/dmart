<script lang="ts">
    import {Accordion, AccordionItem, Button, Card, Checkbox, Input, Label, Select} from "flowbite-svelte";
    import {transformFormToJson, transformJsonToForm} from "@/utils/editors/schemaEditorUtils";
    import {
        addArrayItem,
        addProperty,
        createDefaultSchemaContent,
        removeProperty,
        schemaTypes,
        toggleRequired
    } from "@/utils/schemaFormUtils";


    let {
        content = $bindable({}),
    } : {
        content: any
    } = $props();

    if (!content || Object.keys(content).length === 0) {
        content = createDefaultSchemaContent();
    }

    let formContent = $state(transformJsonToForm(
        $state.snapshot(content)
    ));

    function handleAddProperty(parentPath = "") {
        formContent = addProperty(formContent, parentPath);
    }

    function handleAddArrayItem(parentPath) {
        formContent = addArrayItem(formContent, parentPath);
    }

    function handleRemoveProperty(path, index) {
        formContent = removeProperty(formContent, path, index);
    }

    function handleToggleRequired(propertyName) {
        formContent = toggleRequired(formContent, propertyName);
    }

    function isRequired(propertyName) {
        return formContent.required && formContent.required.includes(propertyName);
    }

    $effect(() => {
        const schemaContent = transformFormToJson(structuredClone(
            $state.snapshot(formContent)
        ));
        content = schemaContent;
    });

</script>

<Card class="p-4 max-w-4xl mx-auto my-2">
    <h2 class="text-xl font-bold mb-4">Schema Editor</h2>

    <!-- Save button removed as changes are applied automatically -->

    <div class="space-y-6">
        <!-- Schema Metadata -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <Label for="schema-title">Schema Title</Label>
                <Input id="schema-title" placeholder="Schema title" bind:value={formContent.title} />
            </div>
            <div>
                <Label for="schema-description">Schema Description</Label>
                <Input id="schema-description" placeholder="Schema description" bind:value={formContent.description} />
            </div>
        </div>

        <!-- Properties -->
        <div class="border p-4 rounded-lg">
            <div class="flex justify-between items-center mb-4">
                <h3 class="font-semibold">Properties</h3>
                <Button size="xs" color="blue" onclick={() => handleAddProperty()}>Add Property</Button>
            </div>

            {#if formContent.properties && formContent.properties.length > 0}
                <Accordion flush>
                    {#each formContent.properties as property, index}
                        <AccordionItem>
                            {#snippet header()}
                                <span class="font-medium">{property.name || 'New Property'}</span>
                                {#if property.type}
                                    <span class="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">{property.type}</span>
                                {/if}
                                {#if isRequired(property.name)}
                                    <span class="ml-2 text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded">Required</span>
                                {/if}
                            {/snippet}

                            <div class="p-2 space-y-4">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <Label for={`property-name-${index}`}>Property Name</Label>
                                        <Input id={`property-name-${index}`} placeholder="Property name" bind:value={property.name} />
                                    </div>
                                    <div>
                                        <Label for={`property-type-${index}`}>Property Type</Label>
                                        <Select id={`property-type-${index}`} bind:value={property.type}>
                                            {#each schemaTypes as type}
                                                <option value={type.value}>{type.name}</option>
                                            {/each}
                                        </Select>
                                    </div>
                                    <div>
                                        <Label for={`property-title-${index}`}>Title</Label>
                                        <Input id={`property-title-${index}`} placeholder="Title" bind:value={property.title} />
                                    </div>
                                    <div>
                                        <Label for={`property-description-${index}`}>Description</Label>
                                        <Input id={`property-description-${index}`} placeholder="Description" bind:value={property.description} />
                                    </div>
                                </div>

                                <!-- Type-specific options -->
                                {#if property.type === 'string'}
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <Label for={`property-minLength-${index}`}>Min Length</Label>
                                            <Input id={`property-minLength-${index}`} type="number" placeholder="Min length" bind:value={property.minLength} />
                                        </div>
                                        <div>
                                            <Label for={`property-maxLength-${index}`}>Max Length</Label>
                                            <Input id={`property-maxLength-${index}`} type="number" placeholder="Max length" bind:value={property.maxLength} />
                                        </div>
                                        <div>
                                            <Label for={`property-pattern-${index}`}>Pattern (regex)</Label>
                                            <Input id={`property-pattern-${index}`} placeholder="Pattern" bind:value={property.pattern} />
                                        </div>
                                        <div>
                                            <Label for={`property-format-${index}`}>Format</Label>
                                            <Select id={`property-format-${index}`} bind:value={property.format}>
                                                <option value="">None</option>
                                                <option value="date-time">Date-Time</option>
                                                <option value="date">Date</option>
                                                <option value="time">Time</option>
                                                <option value="email">Email</option>
                                                <option value="uri">URI</option>
                                            </Select>
                                        </div>
                                    </div>
                                {:else if property.type === 'number' || property.type === 'integer'}
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <Label for={`property-minimum-${index}`}>Minimum</Label>
                                            <Input id={`property-minimum-${index}`} type="number" placeholder="Minimum value" bind:value={property.minimum} />
                                        </div>
                                        <div>
                                            <Label for={`property-maximum-${index}`}>Maximum</Label>
                                            <Input id={`property-maximum-${index}`} type="number" placeholder="Maximum value" bind:value={property.maximum} />
                                        </div>
                                        <div>
                                            <Label for={`property-multipleOf-${index}`}>Multiple Of</Label>
                                            <Input id={`property-multipleOf-${index}`} type="number" placeholder="Multiple of" bind:value={property.multipleOf} />
                                        </div>
                                    </div>
                                {:else if property.type === 'array'}
                                    <div class="border p-3 rounded-md bg-gray-50">
                                        <div class="flex justify-between items-center mb-2">
                                            <h4 class="font-medium">Array Items</h4>
                                            <Button size="xs" color="blue" onclick={() => addArrayItem(`properties.${index}`)}>Configure Items</Button>
                                        </div>

                                        {#if property.items}
                                            <div class="p-2 space-y-3">
                                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    <div>
                                                        <Label for={`items-type-${index}`}>Items Type</Label>
                                                        <Select id={`items-type-${index}`} bind:value={property.items.type}>
                                                            {#each schemaTypes as type}
                                                                <option value={type.value}>{type.name}</option>
                                                            {/each}
                                                        </Select>
                                                    </div>

                                                    {#if property.items.type === 'object' && property.items.properties}
                                                        <div class="col-span-2">
                                                            <Label>Object Properties</Label>
                                                            <div class="border p-2 rounded-md mt-1">
                                                                <Button size="xs" color="blue" onclick={() => handleAddProperty(`properties.${index}.items`)}>Add Object Property</Button>

                                                                {#if property.items.properties.length > 0}
                                                                    {#each property.items.properties as itemProperty, itemIndex}
                                                                        <div class="mt-2 p-2 bg-white rounded border">
                                                                            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                                                <div>
                                                                                    <Label for={`item-property-name-${index}-${itemIndex}`}>Name</Label>
                                                                                    <Input id={`item-property-name-${index}-${itemIndex}`} placeholder="Property name" bind:value={itemProperty.name} />
                                                                                </div>
                                                                                <div>
                                                                                    <Label for={`item-property-type-${index}-${itemIndex}`}>Type</Label>
                                                                                    <Select id={`item-property-type-${index}-${itemIndex}`} bind:value={itemProperty.type}>
                                                                                        {#each schemaTypes as type}
                                                                                            <option value={type.value}>{type.name}</option>
                                                                                        {/each}
                                                                                    </Select>
                                                                                </div>
                                                                            </div>
                                                                            <div class="mt-2 flex justify-end">
                                                                                <Button size="xs" color="red" onclick={() => removeProperty(`properties.${index}.items.properties`, itemIndex)}>Remove</Button>
                                                                            </div>
                                                                        </div>
                                                                    {/each}
                                                                {/if}
                                                            </div>
                                                        </div>
                                                    {/if}
                                                </div>

                                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    <div>
                                                        <Label for={`array-minItems-${index}`}>Min Items</Label>
                                                        <Input id={`array-minItems-${index}`} type="number" placeholder="Min items" bind:value={property.minItems} />
                                                    </div>
                                                    <div>
                                                        <Label for={`array-maxItems-${index}`}>Max Items</Label>
                                                        <Input id={`array-maxItems-${index}`} type="number" placeholder="Max items" bind:value={property.maxItems} />
                                                    </div>
                                                </div>
                                            </div>
                                        {/if}
                                    </div>
                                {:else if property.type === 'object'}
                                    <div class="border p-3 rounded-md bg-gray-50">
                                        <div class="flex justify-between items-center mb-2">
                                            <h4 class="font-medium">Object Properties</h4>
                                            <Button size="xs" color="blue" onclick={() => handleAddProperty(`properties.${index}`)}>Add Object Property</Button>
                                        </div>

                                        {#if property.properties && property.properties.length > 0}
                                            {#each property.properties as nestedProperty, nestedIndex}
                                                <div class="mt-2 p-2 bg-white rounded border">
                                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                        <div>
                                                            <Label for={`nested-property-name-${index}-${nestedIndex}`}>Name</Label>
                                                            <Input id={`nested-property-name-${index}-${nestedIndex}`} placeholder="Property name" bind:value={nestedProperty.name} />
                                                        </div>
                                                        <div>
                                                            <Label for={`nested-property-type-${index}-${nestedIndex}`}>Type</Label>
                                                            <Select id={`nested-property-type-${index}-${nestedIndex}`} bind:value={nestedProperty.type}>
                                                                {#each schemaTypes as type}
                                                                    <option value={type.value}>{type.name}</option>
                                                                {/each}
                                                            </Select>
                                                        </div>
                                                    </div>
                                                    <div class="mt-2 flex justify-end">
                                                        <Button size="xs" color="red" onclick={() => removeProperty(`properties.${index}.properties`, nestedIndex)}>Remove</Button>
                                                    </div>
                                                </div>
                                            {/each}
                                        {/if}
                                    </div>
                                {/if}

                                <div class="flex items-center mt-4">
                                    <Checkbox id={`property-required-${index}`} checked={isRequired(property.name)} onclick={() => toggleRequired(property.name)} />
                                    <Label for={`property-required-${index}`} class="ml-2">Required</Label>
                                </div>

                                <div class="flex justify-end mt-2">
                                    <Button size="xs" color="red" onclick={() => removeProperty('properties', index)}>Remove Property</Button>
                                </div>
                            </div>
                        </AccordionItem>
                    {/each}
                </Accordion>
            {:else}
                <p class="text-gray-500 text-center py-4">No properties defined. Click "Add Property" to start.</p>
            {/if}
        </div>
    </div>
</Card>
