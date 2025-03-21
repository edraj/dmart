<script lang="ts">
  import {
    Button,
    Col,
    Icon,
    Input,
    Row,
    TabContent,
    TabPane,
  } from "sveltestrap";

  let { content = $bindable({})} : {
      content: any
  } = $props();

  let subpaths = $state([{ space: "", subpathList: [""] }]);
  let resource_types = $state([{ value: "" }]);
  let conditions = $state([{ value: "" }]);
  let actions = $state([{ value: "" }]);
  let restricted_fields = $state([{ value: "" }]);
  let allowed_fields_values = $state([{ field: "", values: [""] }]);

  // subpaths
  function convertObjectSubpaths(inputObject) {
    const resultObject = {
      subpaths: {},
    };

    inputObject.forEach((item) => {
      const space = item.space; 
      const subpathList = item.subpathList.filter(s=>s.length);
      if (space) {
        resultObject.subpaths[space] = subpathList;
      }
    });

    return resultObject;
  }
  function addSubpath(index) {
    subpaths[index].subpathList = [...subpaths[index].subpathList, ""];
  }
  function addSpaceSubpath(e) {
    e.preventDefault();
    subpaths = [...subpaths, { space: "", subpathList: [] }];
  }
  function removeSpace(index) {
    subpaths = subpaths.filter((_, i) => i !== index);
  }
  function removeSubpath(space_index, subpath_index) {
    subpaths[space_index].subpathList = subpaths[
      space_index
    ].subpathList.filter((_, i) => i !== subpath_index);
  }
  // ResourceTypes
  function addResourceTypes(e) {
    e.preventDefault();
    resource_types = [...resource_types, { value: "" }];
  }
  function removeResourceTypes(index) {
    resource_types = resource_types.filter((_, i) => i !== index);
  }
  // Conditions
  function addConditions(e) {
    e.preventDefault();
    conditions = [...conditions, { value: "" }];
    content.conditions = conditions.map((i) => i.value).filter((i) => i.length);
  }
  function removeConditions(index) {
    conditions = conditions.filter((_, i) => i !== index);
    content.conditions = conditions.map((i) => i.value).filter((i) => i.length);
  }
  // Actions
  function addActions(e) {
    e.preventDefault();
    actions = [...actions, { value: "" }];
  }
  function removeActions(index) {
    actions = actions.filter((_, i) => i !== index);
  }
  // RestrictedFields
  function addRestrictedFields(e) {
    e.preventDefault();
    restricted_fields = [...restricted_fields, { value: "" }];
  }
  function removeRestrictedFields(index) {
    restricted_fields = restricted_fields.filter((_, i) => i !== index);
  }
  // allowed_fields_values
  function convertObjectAllowValues(inputObject) {
    const resultObject = {
      values: {},
    };

    inputObject.forEach((item) => {
      const field = item.field;
      const values = item.values.filter(v => v.length);

      if (field) {
        resultObject.values[field] = values;
      }      
    });

    return resultObject;
  }
  function addFieldValue(index) {
    allowed_fields_values[index].values = [
      ...allowed_fields_values[index].values,
      "",
    ];
  }
  function addField(e) {
    e.preventDefault();
    allowed_fields_values = [
      ...allowed_fields_values,
      { field: "", values: [] },
    ];
  }
  function removeField(index) {
    allowed_fields_values = allowed_fields_values.filter((_, i) => i !== index);
  }
  function removeFieldValue(field_index, value_index) {
    allowed_fields_values[field_index].values = allowed_fields_values[
      field_index
    ].values.filter((_, i) => i !== value_index);
  }

  $effect(() => {
    if (allowed_fields_values) {
        content.allowed_fields_values = convertObjectAllowValues(
            allowed_fields_values
        ).values;
    }
  });

  $effect(() => {
    if(subpaths){
        content.subpaths = convertObjectSubpaths(subpaths).subpaths;
    }
  });

  $effect(() => {
    if (resource_types) {
        content.resource_types = resource_types
            .map((i) => i.value)
            .filter((i) => i.length);
    }
  });

  $effect(() => {
    if (actions) {
        content.actions = actions.map((i) => i.value).filter((i) => i.length);
    }
  });

  $effect(() =>{
    if(restricted_fields){
        content.restricted_fields = restricted_fields
            .map((i) => i.value)
            .filter((i) => i.length);
    }
  });

  $effect(() => {
    if (conditions) {
        content.conditions = conditions.map((i) => i.value).filter((i) => i.length);
    } 
  });
</script>

<TabContent>
  <TabPane class="py-3" tabId="subpaths" tab="Subpaths" active>
    {#each subpaths as subpath, space_index}
      <div class="input-group mb-3">
        {#if space_index !== 0}
          <Col sm="1" class="text-center align-self-center p-0">
            <Icon
              class="mx-1"
              name="trash-fill"
              onclick={() => removeSpace(space_index)}
              style={"font-size: 1.5rem;"}
            />
          </Col>
        {:else}
          <Col sm="1" class="text-center align-self-center p-0"></Col>
        {/if}
        <Col sm="4">
          <Input
            type="text"
            class="form-control"
            placeholder="Space..."
            bind:value={subpath.space}
          />
        </Col>
        <Col sm="5" class="mx-2">
          {#each subpath.subpathList as _, subpath_index}
            <div class="d-flex">
              <Input
                type="text"
                class="form-control"
                placeholder="Subpath..."
                bind:value={subpath.subpathList}
              />
              <Icon
                class="mx-1"
                name="trash-fill"
                onclick={() => removeSubpath(space_index, subpath_index)}
                style={"font-size: 1.5rem;"}
              />
            </div>
          {/each}
        </Col>
        <Col
          sm="2"
          class="justify-content-center align-self-center p-0"
          style="width: auto"
        >
          <Icon
            class="mx-1"
            name="plus-square-fill"
            onclick={() => addSubpath(space_index)}
            style={"font-size: 1.5rem;"}
          />
        </Col>
      </div>
    {/each}
    <Button color="primary" class="w-100" onclick={addSpaceSubpath}
      >Add Space</Button
    >
  </TabPane>
  <TabPane class="py-3" tabId="resource_types" tab="Resource types">
    {#each resource_types as input, index}
      <Row class="mb-2">
        <Col sm="10"
          ><Input
            type="text"
            class="form-control"
            bind:value={input.value}
            placeholder="Resource type..."
          /></Col
        >
        <Col sm="2" class="align-self-center p-0">
          <Icon
            class="mx-1"
            name="trash-fill"
            onclick={() => removeResourceTypes(index)}
            style={"font-size: 1.5rem;"}
          />
          {#if index === resource_types.length - 1}
            <Icon
              class="mx-1"
              name="plus-square-fill"
              onclick={addResourceTypes}
              style={"font-size: 1.5rem;"}
            />
          {/if}
        </Col>
      </Row>
    {/each}
  </TabPane>
  <TabPane class="py-3" tabId="actions" tab="Actions">
    {#each actions as input, index}
      <Row class="mb-2">
        <Col sm="10"
          ><Input
            type="text"
            class="form-control"
            bind:value={input.value}
            placeholder="Actions..."
          /></Col
        >
        <Col sm="2" class="align-self-center p-0">
          <Icon
            class="mx-1"
            name="trash-fill"
            onclick={() => removeActions(index)}
            style={"font-size: 1.5rem;"}
          />
          {#if index === actions.length - 1}
            <Icon
              class="mx-1"
              name="plus-square-fill"
              onclick={addActions}
              style={"font-size: 1.5rem;"}
            />
          {/if}
        </Col>
      </Row>
    {/each}
  </TabPane>
  <TabPane class="py-3" tabId="conditions" tab="Conditions">
    {#each conditions as input, index}
      <Row class="mb-2">
        <Col sm="10"
          ><Input
            type="text"
            class="form-control"
            bind:value={input.value}
            placeholder="Condition..."
          /></Col
        >
        <Col sm="2" class="align-self-center p-0">
          <Icon
            class="mx-1"
            name="trash-fill"
            onclick={() => removeConditions(index)}
            style={"font-size: 1.5rem;"}
          />
          {#if index === conditions.length - 1}
            <Icon
              class="mx-1"
              name="plus-square-fill"
              onclick={addConditions}
              style={"font-size: 1.5rem;"}
            />
          {/if}
        </Col>
      </Row>
    {/each}
  </TabPane>
  <TabPane class="py-3" tabId="restricted_fields" tab="Restricted fields">
    {#each restricted_fields as input, index}
      <Row class="mb-2">
        <Col sm="10"
          ><Input
            type="text"
            class="form-control"
            bind:value={input.value}
            placeholder="Restricted field..."
          /></Col
        >
        <Col sm="2" class="align-self-center p-0">
          <Icon
            class="mx-1"
            name="trash-fill"
            onclick={() => removeRestrictedFields(index)}
            style={"font-size: 1.5rem;"}
          />
          {#if index === restricted_fields.length - 1}
            <Icon
              class="mx-1"
              name="plus-square-fill"
              onclick={addRestrictedFields}
              style={"font-size: 1.5rem;"}
            />
          {/if}
        </Col>
      </Row>
    {/each}
  </TabPane>
  <TabPane
    class="py-3"
    tabId="allowed_fields_values"
    tab="Allowed fields values"
  >
    {#each allowed_fields_values as allowedFieldsValue, field_index}
      <div class="input-group mb-3">
        {#if field_index !== 0}
          <Col sm="1" class="text-center align-self-center p-0">
            <Icon
              class="mx-1"
              name="trash-fill"
              onclick={() => removeField(field_index)}
              style={"font-size: 1.5rem;"}
            />
          </Col>
        {:else}
          <Col sm="1" class="text-center align-self-center p-0"></Col>
        {/if}
        <Col sm="4">
          <Input
            type="text"
            class="form-control"
            placeholder="Field..."
            bind:value={allowedFieldsValue.field}
          />
        </Col>
        <Col sm="5" class="mx-2">
          {#each allowedFieldsValue.values as _, value_index}
            <div class="d-flex">
              <Input
                type="text"
                class="form-control"
                placeholder="Value..."
                bind:value={allowedFieldsValue.values[value_index]}
              />
              <Icon
                class="mx-1"
                name="trash-fill"
                onclick={() => removeFieldValue(field_index, value_index)}
                style={"font-size: 1.5rem;"}
              />
            </div>
          {/each}
        </Col>
        <Col
          sm="2"
          class="justify-content-center align-self-center p-0"
          style="width: auto"
        >
          <Icon
            class="mx-1"
            name="plus-square-fill"
            onclick={() => addFieldValue(field_index)}
            style={"font-size: 1.5rem;"}
          />
        </Col>
      </div>
    {/each}
    <Button color="primary" class="w-100" onclick={addField}>Add permission</Button>
  </TabPane>
</TabContent>
