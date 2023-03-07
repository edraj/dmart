<script lang="ts">
  import { Col, Container, Row } from "sveltestrap";
  import Header from "../components/Header.svelte";
  // import Footer from "../components/Footer.svelte";
</script>

<Container
  fluid={true}
  class="d-flex flex-column position-relative p-0 my-0 w-100 h-100"
>
  <Row class="align-items-start w-100 ms-0 border border-primary" noGutters>
    <Col sm="12"><Header /></Col>
  </Row>
  <Row class="border border-success w-100 ms-0 my-0" noGutters>
    <Col sm="2" class=" border border-warning">-- Sidebar --</Col>
    <Col sm="10" class="border border-info"><slot /></Col>
  </Row>
  <!--Row class="align-items-end w-100 ms-0 my-0 border border-dark" noGutters>
    <Col sm="12" class=""><Footer /></Col>
  </Row-->
</Container>
