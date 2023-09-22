<script lang="ts">
  import { Card, CardBody, Icon } from "sveltestrap";
</script>

<Card class="w-50 mx-auto my-auto">
  <CardBody
    class="d-flex flex-column justify-content-center align-items-center"
  >
    <Icon name="wifi-off" style="font-size: 10em;" />
    <p style="font-size: 1.5em;">
      Make sure you have a network connection to use this service!
    </p>
  </CardBody>
</Card>
