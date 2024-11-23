<script lang="ts">
  import { Container } from "sveltestrap";
  import Header from "@/components/Header.svelte";
  import Footer from "@/components/Footer.svelte";

  // import Sidebar from "@/components/Sidebar.svelte";
  // import { user } from "@/stores/user";
  // import Login from "@/components/Login.svelte";
  // import { useRegisterSW } from "virtual:pwa-register/svelte";
  //import Offline from "@/components/Offline.svelte";

  let window_height: number = $state(0);
  let header_height: number = $state(0);
  let footer_height: number = $state(0);


  // let isOffline = false;

  /* const { offlineReady, needRefresh, updateServiceWorker } = useRegisterSW({
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

  // $goto("/management/")
</script>

<svelte:window bind:innerHeight={window_height} />
<!--
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
{:else}-->
  <div bind:clientHeight={header_height} class="fixed-top"><Header /></div>
  <Container
    fluid={true}
    class="position-relative pt-4 ps-4 m-2 w-100 overflow-auto"
    style="top: {header_height}px; height: {window_height - header_height - footer_height - 2}px;"
  >
    <slot />
    <!--Row class="h-100 w-100 ms-0 my-0"--> <!-- noGutters-->
      <!--<Col sm="2" class="h-100 overflow-auto"><Sidebar /></Col>-->
      <!--Col sm="12" class="h-100 overflow-auto">
      </Col>
    </Row-->
  </Container>
<!-- {/if} -->
<div bind:clientHeight={footer_height} class="fixed-bottom">
  <Footer />
</div>

