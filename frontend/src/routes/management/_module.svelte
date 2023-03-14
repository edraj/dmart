<!-- routify:meta reset -->
<script lang="ts">
  import { Col, Container, Row } from "sveltestrap";
  import Header from "../../components/management/Header.svelte";
  import Sidebar from "../../components/Sidebar.svelte";
  // import Footer from "../../components/Footer.svelte";
  import signedin_user from "../../stores/signedin_user.js";
  import Login from "../../components/Login.svelte";
  import Notifications from "svelte-notifications";
  import { getSpaces } from "./../../stores/spaces";

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
