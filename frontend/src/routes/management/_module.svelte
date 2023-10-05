<!-- routify:meta reset -->

<script lang="ts">
  import { Col, Container, Row } from "sveltestrap";
  import { user } from "@/stores/user";
  import Login from "@/components/Login.svelte";
  import Header from "@/components/management/Header.svelte";
  import Sidebar from "@/components/management/Sidebar.svelte";
  import { get_profile } from "@/dmart";
  // import { useRegisterSW } from "virtual:pwa-register/svelte";
  import Offline from "@/components/Offline.svelte";
  import TopLoadingBar from "@/components/management/TopLoadingBar.svelte";

  let isOffline = false;

  /*const { offlineReady, needRefresh, updateServiceWorker } = useRegisterSW({
    onRegistered(swr) {
      isOffline = !navigator.onLine;
    },
    onRegisterError(error) {
    },
    onOfflineReady() {
      setTimeout(() => close(), 5000);
    },
  });
  function close() {
    offlineReady.set(false);
    needRefresh.set(false);
  }*/

  let window_height: number;
  let header_height: number;

  $: {
    get_profile();
  }
</script>

<svelte:window bind:innerHeight={window_height} />

<TopLoadingBar />

{#if isOffline}
  <div class="container-fluid d-flex align-items-start py-3 h-100">
    <Offline />
  </div>
{:else if !$user || !$user.signedin}
  <div
    class="container-fluid d-flex align-items-start py-3 h-100"
    id="login-container"
  >
    <Login />
  </div>
{:else}
  <div bind:clientHeight={header_height} class="fixed-top"><Header /></div>
  <Container
    fluid={true}
    class="position-relative p-0"
    style="top: {header_height}px; height: {window_height -
      header_height -
      8}px;"
  >
    <Row class="h-100" noGutters>
      <Col sm="2" class="h-100 border-end border-light px-1"><Sidebar /></Col>
      <Col sm="10" class="h-100 border-end border-light px-1 overflow-auto"
        ><slot />
      </Col>
    </Row>
  </Container>
{/if}
