<script>
  import { JSONEditor } from "svelte-jsoneditor";
  import { faSave } from "@fortawesome/free-regular-svg-icons";

  export let content;
  export let validator;
  export let handleSave = null;

  function handleRenderMenu(items, context) {
    const separator = {
      separator: true,
    };
    if (handleSave) {
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
  }

  export let isSchemaValidated;
  function handleChange(updatedContent, previousContent, patchResult) {
    const v = patchResult.contentErrors.validationErrors;
    if (v === undefined || v.length === 0) {
      isSchemaValidated = true;
    } else {
      isSchemaValidated = false;
    }
  }
</script>

{#if validator}
  <JSONEditor
    bind:content
    bind:validator
    onChange={handleChange}
    onRenderMenu={handleRenderMenu}
  />
{:else}
  <JSONEditor bind:content onRenderMenu={handleRenderMenu} />
{/if}
