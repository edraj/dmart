<script>
  import {
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import { Form, FormGroup, Label, Input } from "sveltestrap";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import { createAjvValidator } from "svelte-jsoneditor";
  import * as schema from "../../../utils/SchemaValidator.json";
  import { dmartCreateSchemas } from "../../../dmart.js";
  import { toastPushSuccess, toastPushFail } from "../../../utils.js";

  const validator = createAjvValidator({ schema });

  let content = {
    json: {
      title: "Schema_Title",
      description: "Schema_Description",
      additionalProperties: false,
      type: "object",
      properties: {},
    },
    text: undefined,
  };
  export let open = false;
  export let props;

  let isSchemaValidated = false;

  function toggle() {
    open = !open;
  }
  async function handleSubmit(event) {
    event.preventDefault();
    if (!isSchemaValidated) {
      return;
    }

    const response = await dmartCreateSchemas(
      fields[0].value,
      fields[1].value,
      JSON.parse(content.text)
    );
    if (response.status === "success") {
      toastPushSuccess();
    } else {
      toastPushFail();
    }
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

<Modal isOpen={open} {toggle} size={"lg"}>
  <ModalHeader />
  <Form on:submit={async (e) => await handleSubmit(e)}>
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
          <hr />
        {/each}
        <ContentJsonEditor
          bind:content
          {validator}
          bind:isSchemaValidated
          handleSave={null}
        />
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
