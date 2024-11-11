<script lang="ts">
  import { Button, Form,  Row, Col } from "sveltestrap";
  import { createEventDispatcher } from "svelte";
  import Captcha from "./Captcha.svelte";
  import { _ } from "@/i18n";
  const dispatch = createEventDispatcher();

  let props = $props();
  let { captcha = false, customSubmit = false, title= "" } = props;
  let valid_captcha = false;
  function onSubmit(event) {

    event.preventDefault();
    if (captcha && !valid_captcha) {
      alert("Kindly fill captcha properly");
      return;
    }

    const fd = new FormData(event.target);
    let record = {};
    for (var pair of fd.entries()) {
      record[pair[0]] = pair[1];
    }
    dispatch("response", record);
  }

</script>

<Form on:submit={onSubmit} class="needs-validation">
  {#if title && title.length != 0}
    <Row form={true}>
      <Col class="text-center">
        <h4>{title}</h4>
      </Col>
    </Row>
  {/if}
  {@render props.children()}
  {#if captcha}
    <Captcha bind:valid={valid_captcha} />
  {/if}
  {#if !customSubmit}
    <Row form={true}>
      <Col class="text-center">
        <Button outline type="submit">{$_("submit")}</Button>
      </Col>
    </Row>
  {/if}
</Form>
