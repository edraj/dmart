<script>
  import { FormFeedback, FormGroup, Label, Input, Row, Col } from "sveltestrap";

  export let id;
  export let type;
  export let title;
  export let placeholder = "";
  export let value = "";
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

<FormGroup row="{true}" class="mx-1 py-0 my-0">
  <Label class="text-start px-1 py-0 m-0" for="{id}" size="sm">{title}</Label>
  <Input
    class="py-0 form-control form-control-sm"
    type="{type}"
    id="{id}"
    name="{id}"
    on:change
    placeholder="{placeholder}"
    readonly="{readonly}"
    bsSize="sm"
    invalid="{!valid && required}"
    bind:value
    valid="{valid}"
    on:input="{handleInput}"
    multiple="{multiple}">
    <slot />
  </Input>
  <!--FormFeedback tooltip={true} {valid}> required </FormFeedback-->
  <!--div class="col-md-1 invalid-feedback text-start">required</div-->
  <!--div class="col-md-1 valid-feedback text-start">something</div-->
</FormGroup>
