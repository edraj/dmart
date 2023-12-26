<script lang="ts">
  import { Col, Row } from "sveltestrap";
  import JsonSchemaChild from "./JsonSchemaChild.svelte";
  // import { JSONEditor, Mode } from "svelte-jsoneditor";
  import {
      addItemsToArrays,
      setProperPropsForObjectOfTypeArray, transformFromProperBodyRequest,
      transformToProperBodyRequest
  } from "@/utils/editors/schemaEditorUtils";
  import {generateUUID} from "@/utils/uuid";
  import {onMount} from "svelte";

  export let content = {json: {}, text: undefined};
  let items = [
      {
          id: generateUUID(),
          name: "root",
          type: "object",
          title: "title",
          description: "",
      },
  ];

  onMount(()=>{
    if (Object.keys(content.json).length !== 0){
        items = [transformFromProperBodyRequest(content.json)];
    }
  });

  // let self;
  function handleRefresh() {
    // if (self) {
      const x = content.json ? structuredClone(content.json) : JSON.parse(content.text);
      delete content.text;
      content.json = {
        ...x,
        ...setProperPropsForObjectOfTypeArray(
          addItemsToArrays(JSON.parse(JSON.stringify(items)))
        )[0],
      };
      transformToProperBodyRequest(content.json);
      content = structuredClone(content);
      // self.set(content);
    // }
  }

  function handleParentRefresh(newParent) {
    items = newParent;
    handleRefresh();
  }
</script>

<Row style="display: flex;justify-content: center;width: 100%;">
  <Col sm={12}>
<!--  <Col sm={4}>-->
<!--    <JSONEditor mode={Mode.text} bind:this={self} bind:content />-->
<!--  </Col>-->
<!--  <Col sm={6}>-->
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
