<!-- routify:meta reset -->
<script lang="ts">
  import {Offcanvas, Container, Row, Col, Collapse, Button} from "sveltestrap";
  import Icon from "@/components/Icon.svelte";
  // import Header from "@/components/Header.svelte";
  // import Footer from "@/components/Footer.svelte";
  // import Sidebar from "@/components/Sidebar.svelte";

  let window_height: number;
  let header_height: number;
  let footer_height: number;

  let isSidebarOpen = false;
  const toggleSidbar = async () => (isSidebarOpen = !isSidebarOpen);
  
  const swipeMin = 50;
  const swipeArea = 20;
  const right = false;
  let touchStart = { x: null, y: null };

  function onTouchStart(e : any) {
    touchStart.x = e.changedTouches[0].clientX;
    touchStart.y = e.changedTouches[0].clientY;
  }

  function onTouchEnd(e : any) {
    const dx = e.changedTouches[0].clientX - touchStart.x;
    const dy = e.changedTouches[0].clientY - touchStart.y;
    const absDx = Math.abs(dx);
    if (absDx > swipeMin) {
      const absDy = Math.abs(dy);
      if (absDy < swipeMin << 1) {
        if ((dx > 0 && right) || (dx < 0 && !right)) {
          isSidebarOpen = false;
        } else if (dx > 0 && touchStart.x <= swipeArea) {
          if (!right) { isSidebarOpen = true; }
        } else if (touchStart.x >= window.innerWidth - swipeArea) {
          if (right) { isSidebarOpen = true; }
        }
      }
    }
  }
</script>
<svelte:body on:touchstart={onTouchStart} on:touchend={onTouchEnd} />
<svelte:window bind:innerHeight={window_height} />




<Offcanvas
  isOpen={isSidebarOpen}
  toggle={toggleSidbar}
  placement="start"
>
  <h1 slot="header">
    <i>Hello <b>World!</b></i>
  </h1>
  Side bar text
</Offcanvas>

<div bind:clientHeight={header_height} class="fixed-top">
  <Button outline color="primary" class="border rounded-3 py-0 ps-0 pe-2" on:click={toggleSidbar}><Icon name="list" class="bi-lg p-1"/>Menu</Button>
  <!--Header /-->


</div>
<Container
  fluid={true}
  class="position-relative p-0 my-0 w-100"
  style="top: {header_height}px; height: {window_height - header_height - footer_height - 2}px;"
>
  <slot />
  <!--Row class="border border-success h-100 w-100 ms-0 my-0" noGutters>
    <Col sm="2" class="h-100 border border-warning overflow-auto"
      ><Sidebar /></Col
    >
    <Col sm="10" class="h-100 border border-info overflow-auto">
      <slot />
    </Col>
  </Row-->
</Container>

<div bind:clientHeight={footer_height} class="fixed-bottom border border-error">
  <!--Footer /-->
</div>
