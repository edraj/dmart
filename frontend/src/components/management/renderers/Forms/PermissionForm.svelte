<script lang="ts">
    import { onMount } from "svelte";
    import { Button, Col, Icon, Input, Row, TabContent, TabPane } from "sveltestrap";

    export let content: any = {};

    // let subpaths = {
    //     "personal": [
    //         "people/__all_subpaths__/protected"
    //     ]
    // };

    let subpaths = [{ space: "", subpathList: [""] }];        
    let resource_types = [{ value: "" }];
    let conditions = [{ value: "" }];
    let actions = [{ value: "" }];
    let restricted_fields = [{ value: "" }];
    let allowed_fields_values = [{ field: "", values: [""] }];

    // ResourceTypes
    function addResourceTypes(e) {
        e.preventDefault();
        resource_types = [...resource_types, { value: "" }];
        content.resource_types = resource_types.map(i=> i.value).filter(i=> i.length);
    }
    function removeResourceTypes(index) {
        resource_types = resource_types.filter((_, i) => i !== index);
        content.resource_types = resource_types.map(i=> i.value).filter(i=> i.length);
    }
    // Conditions
    function addConditions(e) {
        e.preventDefault();
        conditions = [...conditions, { value: "" }];
        content.conditions = conditions.map(i=> i.value).filter(i=> i.length);
    }
    function removeConditions(index) {
        conditions = conditions.filter((_, i) => i !== index);
        content.conditions = conditions.map(i=> i.value).filter(i=> i.length);
    }
    // Actions
    function addActions(e) {
        e.preventDefault();
        actions = [...actions, { value: "" }];
        content.actions = actions.map(i=> i.value).filter(i=> i.length);
    }
    function removeActions(index) {
        actions = actions.filter((_, i) => i !== index);
        content.actions = actions.map(i=> i.value).filter(i=> i.length);
    }
    // RestrictedFields
    function addRestrictedFields(e) {
        e.preventDefault();
        restricted_fields = [...restricted_fields, { value: "" }];
        content.restricted_fields = resource_types.map(i=> i.value).filter(i=> i.length);
    }
    function removeRestrictedFields(index) {
        restricted_fields = restricted_fields.filter((_, i) => i !== index);
        content.restricted_fields = restricted_fields.map(i=> i.value).filter(i=> i.length);
    }
    // subpaths
    function convertObjectSubpaths(inputObject) {
        const resultObject = {
            subpaths: {}
        };

        inputObject.forEach(item => {
            const space = item.space;
            const subpathList = item.subpathList;

            resultObject.subpaths[space] = subpathList;
        });

        return resultObject;
    }
    function addSubpath(index) {
        subpaths[index].subpathList = [
            ...subpaths[index].subpathList, 
            ""
        ];
        content.subpaths = convertObjectSubpaths(subpaths).subpaths;
    }
    function addSpaceSubpath(e) {
        e.preventDefault();
        subpaths = [...subpaths, { space: "", subpathList: [] }];
        content.subpaths = convertObjectSubpaths(subpaths).subpaths;
    }
    function removeSpace(index) {
        subpaths = subpaths.filter((_, i) => i !== index);
        content.subpaths = convertObjectSubpaths(subpaths).subpaths;
    }
    function removeSubpath(space_index, subpath_index) {
        subpaths[space_index].subpathList = subpaths[space_index].subpathList.filter((_, i) => i !== subpath_index);
        content.subpaths = convertObjectSubpaths(subpaths).subpaths;
    }
    // allowed_fields_values
    function convertObjectAllowValues(inputObject) {
        const resultObject = {
            values: {}
        };

        inputObject.forEach(item => {
            const field = item.field;
            const values = item.values;

            resultObject.values[field] = values;
        });

        return resultObject;
    }
    function addFieldValue(index) {
        allowed_fields_values[index].values = [
            ...allowed_fields_values[index].values, 
            ""
        ];
        content.allowed_fields_values = convertObjectAllowValues(allowed_fields_values).values;
    }
    function addField(e) {
        e.preventDefault();
        allowed_fields_values = [...allowed_fields_values, { field: "", values: [] }];
        content.allowed_fields_values = convertObjectAllowValues(allowed_fields_values).values;
    }
    function removeField(index) {
        allowed_fields_values = allowed_fields_values.filter((_, i) => i !== index);
        content.allowed_fields_values = convertObjectAllowValues(allowed_fields_values).values;
    }
    function removeFieldValue(field_index, value_index) {
        allowed_fields_values[field_index].values = allowed_fields_values[field_index].values.filter((_, i) => i !== value_index);
        content.allowed_fields_values = convertObjectAllowValues(allowed_fields_values).values;
    }

</script>

<TabContent>
    <TabPane class="py-3" tabId="subpaths" tab="Subpaths" active>
        {#each subpaths as { space, subpathList }, space_index}
            <div class="input-group mb-3">
                {#if space_index !== 0}
                    <Col sm="1" class="text-center align-self-center p-0">
                        <Icon class="mx-1" name="trash-fill" onclick={() => removeSpace(space_index)} style={"font-size: 1.5rem;"} />
                    </Col>
                {:else}
                <Col sm="1" class="text-center align-self-center p-0"></Col>
                {/if}
                <Col sm="4">
                    <Input type="text" class="form-control" placeholder="Space..." bind:value={space} />
                </Col>
                <Col sm="5" class="mx-2">
                    {#each subpathList as subpath, subpath_index}
                        <div class="d-flex">
                            <Input type="text" class="form-control" placeholder="Subpath..." bind:value={subpath} />
                            <Icon class="mx-1" name="trash-fill" onclick={() => removeSubpath(space_index, subpath_index)} style={"font-size: 1.5rem;"} />
                        </div>
                    {/each}
                </Col>
                <Col sm="2" class="justify-content-center align-self-center p-0" style="width: auto">
                    <Icon class="mx-1" name="plus-square-fill" onclick={()=>addSubpath(space_index)} style={"font-size: 1.5rem;"}/>
                </Col>
            </div>
        {/each}
        <Button color="primary" class="w-100" on:click={addSpaceSubpath}>Add Space</Button>
    </TabPane>
    <TabPane class="py-3" tabId="resource_types" tab="Resource types">
        {#each resource_types as input, index}
            <Row class="mb-2">
                <Col sm="10"><Input type="text" class="form-control" bind:value={input.value} placeholder="Resource type..." /></Col>
                <Col sm="2" class="align-self-center p-0">
                    <Icon class="mx-1" name="trash-fill" onclick={() => removeResourceTypes(index)} style={"font-size: 1.5rem;"} />
                    {#if index == resource_types.length - 1}
                        <Icon class="mx-1" name="plus-square-fill" onclick={addResourceTypes} style={"font-size: 1.5rem;"}/>
                    {/if}
                </Col>
            </Row>
        {/each}
    </TabPane>
    <TabPane class="py-3" tabId="actions" tab="Actions">
        {#each actions as input, index}
            <Row class="mb-2">
                <Col sm="10"><Input type="text" class="form-control" bind:value={input.value} placeholder="Actions..." /></Col>
                <Col sm="2" class="align-self-center p-0">
                    <Icon class="mx-1" name="trash-fill" onclick={() => removeActions(index)} style={"font-size: 1.5rem;"} />
                    {#if index == actions.length - 1}
                        <Icon class="mx-1" name="plus-square-fill" onclick={addActions} style={"font-size: 1.5rem;"}/>
                    {/if}
                </Col>
            </Row>
        {/each}
    </TabPane>
    <TabPane class="py-3" tabId="conditions" tab="Conditions">
        {#each conditions as input, index}
            <Row class="mb-2">
                <Col sm="10"><Input type="text" class="form-control" bind:value={input.value} placeholder="Condition..." /></Col>
                <Col sm="2" class="align-self-center p-0">
                    <Icon class="mx-1" name="trash-fill" onclick={() => removeConditions(index)} style={"font-size: 1.5rem;"} />
                    {#if index == conditions.length - 1}
                        <Icon class="mx-1" name="plus-square-fill" onclick={addConditions} style={"font-size: 1.5rem;"}/>
                    {/if}
                </Col>
            </Row>
        {/each}
    </TabPane>
    <TabPane class="py-3" tabId="restricted_fields" tab="Restricted fields">
        {#each restricted_fields as input, index}
            <Row class="mb-2">
                <Col sm="10"><Input type="text" class="form-control" bind:value={input.value} placeholder="Restricted field..." /></Col>
                <Col sm="2" class="align-self-center p-0">
                    <Icon class="mx-1" name="trash-fill" onclick={() => removeRestrictedFields(index)} style={"font-size: 1.5rem;"} />
                    {#if index == conditions.length - 1}
                        <Icon class="mx-1" name="plus-square-fill" onclick={addRestrictedFields} style={"font-size: 1.5rem;"}/>
                    {/if}
                </Col>
            </Row>
        {/each}
    </TabPane>
    <TabPane class="py-3" tabId="allowed_fields_values" tab="Allowed fields values">
        {#each allowed_fields_values as { field, values }, field_index}
            <div class="input-group mb-3">
                {#if field_index !== 0}
                    <Col sm="1" class="text-center align-self-center p-0">
                        <Icon class="mx-1" name="trash-fill" onclick={() => removeField(field_index)} style={"font-size: 1.5rem;"} />
                    </Col>
                {:else}
                <Col sm="1" class="text-center align-self-center p-0"></Col>
                {/if}
                <Col sm="4">
                    <Input type="text" class="form-control" placeholder="Field..." bind:value={field} />
                </Col>
                <Col sm="5" class="mx-2">
                    {#each values as value, value_index}
                        <div class="d-flex">
                            <Input type="text" class="form-control" placeholder="Value..." bind:value={value} />
                            <Icon class="mx-1" name="trash-fill" onclick={() => removeFieldValue(field_index, value_index)} style={"font-size: 1.5rem;"} />
                        </div>
                    {/each}
                </Col>
                <Col sm="2" class="justify-content-center align-self-center p-0" style="width: auto">
                    <Icon class="mx-1" name="plus-square-fill" onclick={()=>addFieldValue(field_index)} style={"font-size: 1.5rem;"}/>
                </Col>
            </div>
        {/each}
        <Button color="primary" class="w-100" on:click={addField}>Add Field</Button>
    </TabPane>
</TabContent>
