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

  let init = getSpaces();
</script>

<Notifications>
  {#if !$signedin_user}
    <div id="login-container">
      <Login />
    </div>
  {:else}
    {#await init}
      <div />
    {:then _}
      <Container
        fluid={true}
        class="d-flex flex-column position-relative p-0 my-0 w-100 h-100"
      >
        <Row
          class="align-items-start w-100 ms-0 border border-primary"
          noGutters
        >
          <Col sm="12"><Header /></Col>
        </Row>
        <Row class="w-100 ms-0 my-0 border border-success h-100" noGutters>
          <Col
            sm="2"
            class="d-flex flex-column justify-content-between fixed-size border border-warning bg-light"
            ><Sidebar /></Col
          >

          <Col sm="10" class="fixed-size border border-info"><slot /></Col>
        </Row>
        <!--Row class="align-items-end w-100 ms-0 my-0 border border-dark" noGutters>
        <Col sm="12" class=""><Footer /></Col>
      </Row-->
      </Container>
      <style>
        .fixed-size {
          height: 95vh;
          overflow-y: scroll;
          top: 0;
          bottom: 0;
          -ms-overflow-style: none; /* IE and Edge */
          scrollbar-width: none; /* Firefox */
        }

        /* Hide scrollbar for Chrome, Safari and Opera */
        .fixed-size::-webkit-scrollbar {
          display: none;
        }
      </style>
    {:catch error}
      <p style="color: red">{error.message}</p>
    {/await}
  {/if}
</Notifications>

<style>
  #login-container {
    display: flex;
    height: 100vh;
  }
</style>
