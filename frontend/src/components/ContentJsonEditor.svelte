<script>
  import { JSONEditor } from "svelte-jsoneditor";
  import { faSave } from "@fortawesome/free-regular-svg-icons";

  export let content;
  export let handleSave;

  function handleRenderMenu(items, context) {
    const separator = {
      separator: true,
    };
    const saveButton = {
      onClick: handleSave,
      icon: faSave,
      title: "Save",
    };

    const itemsWithoutSpace = items.slice(0, items.length - 2);
    return itemsWithoutSpace.concat([
      separator,
      saveButton,
      {
        space: true,
      },
    ]);
  }
</script>

<JSONEditor bind:content onRenderMenu={handleRenderMenu} />
