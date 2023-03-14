<script>
  import {
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import { Form, FormGroup, Label, Input } from "sveltestrap";

  export let open = false;
  export let size = undefined;
  export let props;
  export let handleModelSubmit;

  function toggle() {
    open = !open;
  }
  function handleSubmit(event) {
    event.preventDefault();
    handleModelSubmit(fields);
  }

  const fields = props.map((p) => {
    return {
      type: "input",
      name: p.name,
      placeholder: p.name + "...",
      value: p.value ?? "",
      rules: ["required"],
      messages: {
        required: "This field is required!",
      },
    };
  });
</script>

<Modal isOpen={open} {toggle} {size}>
  <ModalHeader />
  <Form on:submit={handleSubmit}>
    <ModalBody>
      <FormGroup>
        {#each fields as field}
          <Label>{field.name}</Label>
          <Input
            name={field.name}
            placeholder={field.placeholder}
            required
            bind:value={field.value}
          />
        {/each}
      </FormGroup>
    </ModalBody>
    <ModalFooter>
      <Button type="button" color="secondary" on:click={() => (open = false)}
        >cancel</Button
      >
      <Button type="submit" color="primary">Submit</Button>
    </ModalFooter>
  </Form>
</Modal>
