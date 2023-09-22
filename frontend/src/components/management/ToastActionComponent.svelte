<script>
  	import { toast } from '@zerodevx/svelte-toast'
  import { Col, Row, Container, Button } from "sveltestrap";
  export let toastId
  export let action;
  export let message;

  const handleClose = () => toast.pop(toastId);
  const handleAction = () => {
    action();
    toast.pop(toastId);
  }
</script>

<div class="wrap">
  <Container>
    <Col>
      <Row><p>{message}</p></Row>
      <Row>
        <Col class={'d-flex justify-content-start'}><Button color={"primary"} on:click={handleAction}>Fix it</Button></Col>
        <Col class={'d-flex justify-content-end'}><Button color={"secondary"} on:click={handleClose}>Close</Button></Col>
      </Row>
    </Col>
  </Container>
</div>

<style>
  .wrap {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
</style>
