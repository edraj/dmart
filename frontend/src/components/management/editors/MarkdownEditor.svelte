<script>
  import { Container, Row, Col } from "sveltestrap";
  import { createEventDispatcher } from "svelte";
  import { marked } from "marked";

  const dispatch = createEventDispatcher();

  export let content;
  $: {
    if (typeof content === "object") {
      content = JSON.stringify(content);
    }
  }
</script>

<Container fluid={true} class="h-100 pt-1">
  <Row class="h-100">
    <Col sm="6" class="h-100">
      <textarea
        rows="10"
        maxlength="4096"
        class="h-100 w-100 m-0 font-monospace form-control form-control-sm"
        bind:value={content}
        on:input={() => dispatch("changed")}
      />
    </Col>
    <Col sm="6" class="h-100">
      <div class="h-100 w-100" style="overflow: hidden auto">
        {@html marked(content)}
      </div>
    </Col>
  </Row>
</Container>

<style global>
</style>
