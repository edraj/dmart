<!-- routify:meta reset -->
<script lang="ts">
  import { Col, Container, Row } from "sveltestrap";
  // import Footer from "../../_components/Footer.svelte";
  import signedin_user from "./_stores/signedin_user.js";
  import Login from "../_components/Login.svelte";
  import Notifications from "svelte-notifications";
  import { getSpaces } from "./_stores/spaces";
  import Header from "./_components/Header.svelte";
  import Sidebar from "./_components/Sidebar.svelte";

  getSpaces();
</script>

<Notifications>
  {#if !$signedin_user}
    <div
      class="container-fluid d-flex align-items-start py-3"
      id="login-container"
    >
      <Login />
    </div>
  {:else}
    <Container
      fluid={true}
      class="d-flex flex-column position-relative p-0 my-0 w-100 h-100"
    >
      <Row class="align-items-start w-100 ms-0 border border-primary" noGutters>
        <Col sm="12"><Header /></Col>
      </Row>
      <Row class="w-100 ms-0 my-0 border border-success h-100" noGutters>
        <Col sm="2" class=" border border-warning"><Sidebar /></Col>
        <Col sm="10" class="border border-info"><slot /></Col>
      </Row>
      <!--Row class="align-items-end w-100 ms-0 my-0 border border-dark" noGutters>
        <Col sm="12" class=""><Footer /></Col>
      </Row-->
    </Container>
  {/if}
</Notifications>
