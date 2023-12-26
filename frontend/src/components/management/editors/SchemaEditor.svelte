<script lang="ts">
  import { Col, Row } from "sveltestrap";
  import JsonSchemaChild from "./JsonSchemaChild.svelte";
  import { JSONEditor, Mode } from "svelte-jsoneditor";
  import { addItemsToArrays, setProperPropsForObjectOfTypeArray } from "@/utils/editors/schemaEditorUtils";

  export let content;
  export let items;

  let self;
  function handleRefresh() {
    if (self) {
      const x = content.json ? structuredClone(content.json) : JSON.parse(content.text);
      delete content.text;
      content.json = {
        ...x,
        ...setProperPropsForObjectOfTypeArray(
          addItemsToArrays(JSON.parse(JSON.stringify(items)))
        ),
      };
      self.set(content);
    }
  }

  function handleParentRefresh(newParent) {
    items = newParent;
  }
</script>

<Row style="display: flex;justify-content: center;width: 100%;">
  <Col sm={4}>
    <JSONEditor mode={Mode.text} bind:this={self} bind:content />
  </Col>
  <Col sm={6}>
    {#key items}
      {#each items as item}
        <JsonSchemaChild
          {item}
          parent={items}
          refresh={handleRefresh}
          parentRefresh={handleParentRefresh}
          root={true}
        />
      {/each}
    {/key}
  </Col>
</Row>
