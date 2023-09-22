<script lang="ts" >
 import {marked} from "marked";

 const md =   `
# Setup
Here are the steps to set up svelte-marked plugin
1. Install it
2. Enjoy
    - If you enjoyed, make sure to star the repo!
`;

</script>

{@html marked.parse(md)}


