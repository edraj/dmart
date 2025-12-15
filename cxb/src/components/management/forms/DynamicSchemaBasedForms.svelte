<script lang="ts">
    import {Accordion, AccordionItem, Button, Card, Checkbox, Input, Label, Select, Textarea} from "flowbite-svelte";
    import {onMount} from "svelte";

    let {
        content = $bindable({}),
        schema,
    } : {
        content: any,
        schema: any,
    } = $props();

    onMount(() => {
        if (schema && schema.properties) {
            initializeContent(schema.properties);
        }
    });

    function initializeContent(properties) {
        for (const key in properties) {
            const prop = properties[key];

            if (content[key] !== undefined) continue;

            if (prop.type === 'string') {
                content[key] = prop.default || '';
            } else if (prop.type === 'number' || prop.type === 'integer') {
                content[key] = prop.default !== undefined ? prop.default : null;
            } else if (prop.type === 'boolean') {
                content[key] = prop.default || false;
            } else if (prop.type === 'array') {
                content[key] = prop.default || [];
            } else if (prop.type === 'object' && prop.properties) {
                content[key] = {};
                initializeContent(prop.properties);
            } else {
                content[key] = null;
            }
        }

        content = { ...content };
    }

    function addArrayItem(path) {
        let target = content;
        const parts = path.split('.');

        for (let i = 0; i < parts.length; i++) {
            if (!target[parts[i]]) {
                target[parts[i]] = [];
            }
            target = target[parts[i]];
        }

        let schemaProp = schema.properties;
        for (let i = 0; i < parts.length; i++) {
            if (schemaProp[parts[i]]) {
                schemaProp = schemaProp[parts[i]];
            }
        }

        let newItem = {};
        if (schemaProp.items && schemaProp.items.type === 'object' && schemaProp.items.properties) {
            for (const key in schemaProp.items.properties) {
                const prop = schemaProp.items.properties[key];
                if (prop.type === 'string') {
                    newItem[key] = '';
                } else if (prop.type === 'number' || prop.type === 'integer') {
                    newItem[key] = null;
                } else if (prop.type === 'boolean') {
                    newItem[key] = false;
                } else if (prop.type === 'array') {
                    newItem[key] = [];
                } else if (prop.type === 'object') {
                    newItem[key] = {};
                } else {
                    newItem[key] = null;
                }
            }
        } else if (schemaProp.items) {
            if (schemaProp.items.type === 'string') {
                newItem = '';
            } else if (schemaProp.items.type === 'number' || schemaProp.items.type === 'integer') {
                newItem = null;
            } else if (schemaProp.items.type === 'boolean') {
                newItem = false;
            } else {
                newItem = null;
            }
        }

        target.push(newItem);

        content = { ...content };
    }

    function removeArrayItem(path, index) {
        let target = content;
        const parts = path.split('.');

        for (let i = 0; i < parts.length - 1; i++) {
            if (!target[parts[i]]) return;
            target = target[parts[i]];
        }

        const lastPart = parts[parts.length - 1];
        if (!target[lastPart]) return;

        target[lastPart].splice(index, 1);

        content = { ...content };
    }

    function getSchemaProperty(path) {
        if (!schema || !schema.properties) return null;

        const parts = path.split('.');
        let current = schema.properties;

        for (const part of parts) {
            if (!current[part]) return null;
            current = current[part];

            if (current.type === 'array' && parts.indexOf(part) < parts.length - 1) {
                current = current.items.properties;
            } else if (current.type === 'object' && current.properties) {
                current = current.properties;
            }
        }

        return current;
    }

    function isRequired(propertyName) {
        return schema.required && schema.required.includes(propertyName);
    }
</script>

<Card class="p-4 max-w-4xl mx-auto my-2">
    {#if schema && schema.properties}
        <h2 class="text-xl font-bold mb-4">{schema.title || 'Form'}</h2>
        {#if schema.description}
            <p class="text-gray-600 mb-4">{schema.description}</p>
        {/if}

        <div class="space-y-6">
            {#each Object.keys(schema.properties) as propName}
                {@const property = schema.properties[propName]}
                <div class="mb-4">
                    <Label for={propName} class="mb-2">
                        {#if isRequired(propName)}
                            <span class="text-red-500 text-lg" style="vertical-align: center">*</span>
                        {/if}
                        {property.title || propName}
                    </Label>

                    {#if property.description}
                        <p class="text-xs text-gray-500 mb-1">{property.description}</p>
                    {/if}

                    {#if property.type === 'string'}
                        {#if property.format === 'date-time' || property.format === 'date'}
                            <Input 
                                id={propName} 
                                type="date" 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                            />
                        {:else if property.format === 'time'}
                            <Input 
                                id={propName} 
                                type="time" 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                            />
                        {:else if property.format === 'email'}
                            <Input 
                                id={propName} 
                                type="email" 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                            />
                        {:else if property.format === 'uri'}
                            <Input 
                                id={propName} 
                                type="url" 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                            />
                        {:else if property.enum}
                            <Select 
                                id={propName} 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                            >
                                <option value="">Select an option</option>
                                {#each property.enum as option}
                                    <option value={option}>{option}</option>
                                {/each}
                            </Select>
                        {:else if property.maxLength && property.maxLength > 100}
                            <Textarea 
                                id={propName} 
                                rows={3} 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                            />
                        {:else}
                            <Input 
                                id={propName} 
                                type="text" 
                                bind:value={content[propName]} 
                                required={isRequired(propName)}
                                minlength={property.minLength}
                                maxlength={property.maxLength}
                                pattern={property.pattern}
                            />
                        {/if}
                    {:else if property.type === 'number' || property.type === 'integer'}
                        <Input 
                            id={propName} 
                            type="number" 
                            bind:value={content[propName]} 
                            required={isRequired(propName)}
                            min={property.minimum}
                            max={property.maximum}
                            step={property.type === 'integer' ? 1 : (property.multipleOf || 'any')}
                        />
                    {:else if property.type === 'boolean'}
                        <div class="flex items-center gap-2">
                            <Checkbox 
                                id={propName} 
                                bind:checked={content[propName]}
                            />
                        </div>
                    {:else if property.type === 'array'}
                        <div class="border p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-2">
                                <h3 class="font-semibold">{property.title || propName}</h3>
                                <Button size="xs" color="blue" onclick={() => addArrayItem(propName)}>Add Item</Button>
                            </div>

                            {#if content[propName] && content[propName].length > 0}
                                {#each content[propName] as item, index}
                                    <div class="mt-2 p-2 bg-gray-50 rounded border">
                                        {#if property.items.type === 'object' && property.items.properties}
                                            <div class="grid grid-cols-1 gap-2">
                                                {#each Object.keys(property.items.properties) as itemPropName}
                                                    {@const itemProperty = property.items.properties[itemPropName]}
                                                    <div>
                                                        <Label for={`${propName}-${index}-${itemPropName}`} class="text-sm">
                                                            {itemProperty.title || itemPropName}
                                                        </Label>
                                                        
                                                        {#if itemProperty.type === 'string'}
                                                            {#if itemProperty.enum}
                                                                <Select 
                                                                    id={`${propName}-${index}-${itemPropName}`} 
                                                                    bind:value={item[itemPropName]}
                                                                >
                                                                    {#each itemProperty.enum as option}
                                                                        <option value={option}>{option}</option>
                                                                    {/each}
                                                                </Select>
                                                            {:else}
                                                                <Input 
                                                                    id={`${propName}-${index}-${itemPropName}`} 
                                                                    bind:value={item[itemPropName]}
                                                                />
                                                            {/if}
                                                        {:else if itemProperty.type === 'number' || itemProperty.type === 'integer'}
                                                            <Input 
                                                                id={`${propName}-${index}-${itemPropName}`} 
                                                                type="number" 
                                                                bind:value={item[itemPropName]}
                                                            />
                                                        {:else if itemProperty.type === 'boolean'}
                                                            <Checkbox 
                                                                id={`${propName}-${index}-${itemPropName}`} 
                                                                bind:checked={item[itemPropName]}
                                                            />
                                                        {/if}
                                                    </div>
                                                {/each}
                                            </div>
                                        {:else}
                                            {#if property.items.type === 'string'}
                                                {#if property.items.enum}
                                                    <Select bind:value={content[propName][index]}>
                                                        {#each property.items.enum as option}
                                                            <option value={option}>{option}</option>
                                                        {/each}
                                                    </Select>
                                                {:else}
                                                    <Input bind:value={content[propName][index]} />
                                                {/if}
                                            {:else if property.items.type === 'number' || property.items.type === 'integer'}
                                                <Input type="number" bind:value={content[propName][index]} />
                                            {:else if property.items.type === 'boolean'}
                                                <Checkbox bind:checked={content[propName][index]} />
                                            {/if}
                                        {/if}
                                        
                                        <div class="flex justify-end mt-2">
                                            <Button size="xs" color="red" onclick={() => removeArrayItem(propName, index)}>Remove</Button>
                                        </div>
                                    </div>
                                {/each}
                            {:else}
                                <p class="text-gray-500 text-center py-2">No items added yet.</p>
                            {/if}
                        </div>
                    {:else if property.type === 'object' && property.properties}
                        <Accordion flush>
                            <AccordionItem>
                                <span slot="header" class="font-medium">{property.title || propName}</span>
                                <div class="p-2 space-y-3">
                                    {#each Object.keys(property.properties) as nestedPropName}
                                        {@const nestedProperty = property.properties[nestedPropName]}
                                        <div class="mb-3">
                                            <Label for={`${propName}-${nestedPropName}`} class="text-sm">
                                                {nestedProperty.title || nestedPropName}
                                            </Label>
                                            
                                            {#if nestedProperty.type === 'string'}
                                                <Input 
                                                    id={`${propName}-${nestedPropName}`} 
                                                    bind:value={content[propName][nestedPropName]}
                                                />
                                            {:else if nestedProperty.type === 'number' || nestedProperty.type === 'integer'}
                                                <Input 
                                                    id={`${propName}-${nestedPropName}`} 
                                                    type="number" 
                                                    bind:value={content[propName][nestedPropName]}
                                                />
                                            {:else if nestedProperty.type === 'boolean'}
                                                <Checkbox 
                                                    id={`${propName}-${nestedPropName}`} 
                                                    bind:checked={content[propName][nestedPropName]}
                                                />
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            </AccordionItem>
                        </Accordion>
                    {/if}
                </div>
            {/each}
        </div>
    {:else}
        <p class="text-gray-500 text-center py-4">No schema provided or schema has no properties.</p>
    {/if}
</Card>

