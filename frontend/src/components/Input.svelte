<script lang="ts">
  import { FormFeedback, FormGroup, Label, Input, Row, Col } from "sveltestrap";

  export let id;
  export let type;
  export let title;
  export let placeholder = "";
  export let value: any = "";
  export let required = false;
  export let multiple = false;
  export let readonly = false;

  let valid = false;
  function handleInput(event) {
    if (type == "email") {
      valid = /^[^@]+@[^@]+$/.test(event.target.value) || !required;
    } else {
      valid = event.target.value.length > 0 || !required;
    }
  }
</script>

<FormGroup row={true} class="mx-1 py-0 my-0">
  {#if type !== "checkbox"}
    <Label class="text-start px-1 py-0 m-0" for={id} size="sm">{title}</Label>
  {/if}
  <Input
    class="py-0 form-control form-control-sm"
    {type}
    {id}
    checked={type === "checkbox" ? value : false}
    label={type === "checkbox" ? title : ""}
    name={id}
    on:change
    {placeholder}
    {readonly}
    bsSize="sm"
    invalid={!valid && required}
    bind:value
    {valid}
    on:input={handleInput}
    {multiple}
  >
    <slot />
  </Input>
  <!--FormFeedback tooltip={true} {valid}> required </FormFeedback-->
  <!--div class="col-md-1 invalid-feedback text-start">required</div-->
  <!--div class="col-md-1 valid-feedback text-start">something</div-->
</FormGroup>
