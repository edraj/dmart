<script lang="ts">
  import { Button, Icon, Modal } from 'sveltestrap';
  let message: string = "Nice day";
  let isOpen = false;
  const toggle = () => (isOpen = !isOpen);
</script>

{message}


<Button color="primary">
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
