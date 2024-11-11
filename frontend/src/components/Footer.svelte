<script lang="ts">
    import {Dropdown, DropdownItem, DropdownMenu, DropdownToggle, Navbar, NavbarBrand} from "sveltestrap";
  import SelectLanguage from "./SelectLanguage.svelte";
  import LocalizedValue from "./LocalizedValue.svelte";
  import { website } from "@/config";
  import Icon from "@/components/Icon.svelte";
    import {handleThemeChange, themesList} from "@/stores/themes_store";
</script>

<Navbar class=" px-3 mt-0 py-0" color="light" light>
  <SelectLanguage />
  <!--LocalizedValue field="{website.footer}" /-->
  <!--NavbarBrand href="/" ><LocalizedValue field="{website.display_name}" /></NavbarBrand-->
  <NavbarBrand href="https://github.com/edraj/dmart" title="github" class="ms-auto"><Icon name="github" class="text-secondary"/></NavbarBrand>
  <NavbarBrand href="mailto:kefah.issa@gmail.com" title="eMail"><Icon name="envelope-at" class="text-secondary"/></NavbarBrand>
  <NavbarBrand href="https://matrix.to/#/#discussions:dmart.cc" title="Public chat on Matrix"><Icon name="chat-left-text" class="text-secondary"/></NavbarBrand>
<!--  <Dropdown>-->
<!--    <DropdownToggle><Icon name="palette-fill" /></DropdownToggle>-->
<!--    <DropdownMenu end>-->
<!--      {#each themesList as theme}-->
<!--        <DropdownItem name={theme} onclick={handleThemeChange}>{theme}</DropdownItem>-->
<!--      {/each}-->
<!--    </DropdownMenu>-->
<!--  </Dropdown>-->
</Navbar>
