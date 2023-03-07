<script>
  import { JSONEditor } from "svelte-jsoneditor";

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
  $: console.log("contents changed:", content);
</script>

<div>
  <!--JSONEditor bind:json /-->
  <JSONEditor bind:content />
</div>
