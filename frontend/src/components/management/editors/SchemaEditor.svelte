<script lang="ts">
  import { Col, Row } from "sveltestrap";
  import JsonSchemaChild from "./JsonSchemaChild.svelte";
  import {
    transformFromProperBodyRequest,
    transformToProperBodyRequest
  } from "@/utils/editors/schemaEditorUtils";
  import {generateUUID} from "@/utils/uuid";
  // import {JSONEditor, Mode} from "svelte-jsoneditor";
  // import Prism from "@/components/Prism.svelte";

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


  if (Object.keys(content.json).length !== 0){
      const _items = transformFromProperBodyRequest(content.json)
      _items.name = "root"
      items = [_items];
  }

  const cleanUpProps = [
      "minimum", "maximum", "minLength", "maxLength",
      "minItems", "maxItems", "uniqueItems", "pattern",
      "isRequired",
  ];
  function cleanUp(content) {
        for (let prop in content) {
            if (content.hasOwnProperty(prop)) {
                if (typeof content[prop] === 'object' && content[prop] !== null) {
                    cleanUp(content[prop]);
                    if (Object.keys(content[prop]).length === 0) {
                        delete content[prop];
                    }
                } else if (cleanUpProps.includes(prop) && content[prop] === '') {
                   delete content[prop];
                }
            }
        }
  }

  // let self;
  function handleRefresh() {
    // if (self) {
      content.json = structuredClone(items)[0];
      cleanUp(content.json);
      transformToProperBodyRequest(content.json);
      content = structuredClone(content);
      // self.set(content);
    // }
  }

  function handleParentRefresh(newParent) {
    items = [...newParent];
  }
</script>

<Row style="display: flex;justify-content: center;width: 100%;">
  <Col sm={12}>
<!--  <Prism bind:code={items}/>-->
<!--  <Col sm={4}>-->
<!--    <JSONEditor mode={Mode.text} bind:this={self} bind:content />-->
<!--  </Col>-->
<!--  <Col sm={6}>-->
      {#each items as item}
        <JsonSchemaChild
          item={item}
          parent={items}
          refresh={handleRefresh}
          parentRefresh={handleParentRefresh}
          root={true}
        />
      {/each}
  </Col>
</Row>
