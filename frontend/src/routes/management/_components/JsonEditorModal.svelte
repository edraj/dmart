<script>
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import {
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import { Form, FormGroup } from "sveltestrap";

  export let open = false;
  export let handleModelSubmit;
  export let content;

  function toggle() {
    open = !open;
  }
  function handleSubmit(event) {
    event.preventDefault();
    handleModelSubmit(content);
  }
</script>

<Modal isOpen={open} {toggle} size={"lg"}>
  <ModalHeader />
  <Form on:submit={handleSubmit}>
    <ModalBody>
      <FormGroup>
        <ContentJsonEditor bind:content />
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
