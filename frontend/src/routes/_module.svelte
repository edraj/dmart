<script lang="ts">
  import { goto } from "@roxi/routify";
  import { Col, Container, Row } from "sveltestrap";
  import Header from "./management/_components/Header.svelte";
  // import Footer from "../_components/Footer.svelte";
  $goto("/management/dashboard");
</script>

<Container fluid={false} class="d-flex flex-column position-relative p-0 my-1">
  <Row class="align-items-start w-100 ms-0 border border-primary" noGutters>
    <Col sm="12"><Header /></Col>
  </Row>
  <Row class="border border-success w-100 ms-0 my-0" noGutters>
    <Col sm="2" class="fix border border-warning">-- Sidebar --</Col>
    <Col sm="10" class="border border-info"><slot /></Col>
  </Row>
  <!--Row class="align-items-end w-100 ms-0 my-0 border border-dark" noGutters>
    <Col sm="12" class=""><Footer /></Col>
  </Row-->
</Container>
