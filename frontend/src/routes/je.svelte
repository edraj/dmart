<script>
  import { createAjvValidator, JSONEditor } from "svelte-jsoneditor";
  import * as schema from "./../utils/SchemaValidator.json";

  const validator = createAjvValidator({ schema });

  let onError;
  let data = {
    array: [1, 2, 3],
    boolean: true,
    color: "#82b92c",
    null: null,
    number: 123,
    object: { a: "b", c: "d" },
    string: "Hello World!!",
  };

  let content = {
    json: data,
    text: undefined,
  };
  $: console.log("contents changed:", onError);

  function handleChange(updatedContent, previousContent, patchResult) {
    // content is an object { json: JSONData } | { text: string }
    console.log("onChange: ", patchResult.contentErrors.validationErrors);
    content = updatedContent;
  }

  let refJsonEditor;

  $: {
    refJsonEditor?.expand(() => false);
  }
</script>

<div>
  <!--JSONEditor bind:json /-->
  <JSONEditor
    bind:content
    {validator}
    onChange={handleChange}
    bind:this={refJsonEditor}
  />
</div>
