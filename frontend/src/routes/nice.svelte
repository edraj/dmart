<script lang="ts">
  import { Button, Icon, Modal } from "sveltestrap";
  import { Level, showToast } from "../utils/toast";

  let message: string = "Nice day";
  let isOpen = false;

  async function toggle() {
    isOpen = !isOpen;
  }
  const mytoast = () => showToast(Level.warn, "Hello");

  export let context;
  const { node } = context;
</script>

{message}

<Button color="primary" on:click={mytoast}>
  Nice! <Icon name="emoji-smile-fill" />
</Button>

<Button color="primary" on:click={toggle}>Hello World!</Button>
<Modal body {isOpen} {toggle} header="Hello World!">
  <p>There's a song that we're singing. Come on</p>
  <img
    src="https://i.ytimg.com/vi/NUJIRujygvY/hqdefault.jpg"
    alt="Come on Get Happy"
    class="img-fluid"
  />
</Modal>

<h2>{node.name}</h2>
<pre> {JSON.stringify(node, null, 2)} </pre>
<h1>{JSON.stringify(node.meta)}</h1>
