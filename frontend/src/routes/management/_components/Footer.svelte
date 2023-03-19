<script>
  import { Navbar, NavbarBrand } from "sveltestrap";
  import SelectLanguage from "./SelectLanguage.svelte";
  import LocalizedValue from "./LocalizedValue.svelte";
  import { website } from "../../../config.js";
</script>

<Navbar class=" px-0 py-0 mt-0 " color="light" light>
  <SelectLanguage />
  <LocalizedValue field={website.footer} />
  <NavbarBrand href="/">
    <LocalizedValue field={website.display_name} />
  </NavbarBrand>
</Navbar>
