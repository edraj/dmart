<script lang="ts">
  import { Form, Input, Button, Navbar, NavbarBrand, Nav, NavLink } from "sveltestrap";
  import { _ } from "@/i18n";
  import { website } from "@/config";
  import Icon from "@/components/Icon.svelte";
  // import signedin_user from "../management/_stores/signedin_user";
  import { user, signout } from "@/stores/user";
  // import { redirect } from "@roxi/routify";
  import LocalizedValue from "./LocalizedValue.svelte";

  let search : string = "";
  function handleClick(event: Event) {
     event.preventDefault();
  //   $redirect(`/search/posts?q=${encodeURI(search)}`);
  }

</script>

<Navbar color="light" light expand="md" class="px-2 w-100 py-0">
  <NavbarBrand href="/"><LocalizedValue field="{website.short_name}" /></NavbarBrand>
  <Nav class="me-auto" navbar>
    {#if $user && $user.signedin}
      <NavLink href="/management/content">{$user.localized_displayname}</NavLink>
    {/if}
    <NavLink href="/about">{$_("about")}</NavLink>
    <NavLink href="/contact">{$_("contact_us")}</NavLink>
    {#if !$user || !$user.signedin}
      <NavLink href="/management">{$_("login")}</NavLink>
    {:else}
      <NavLink href="#" title="{$_('logout')}" on:click="{signout}">
        <Icon name="power" />
      </NavLink>
    {/if}
  </Nav>
  <Form inline={true} class="ms-auto d-flex my-2 my-lg-0">
    <Input
      bsSize="sm"
      type="search"
      readonly={false}
      placeholder={$_('searching_for_what')}
      class=" ms-sm-2 "
      bind:value={search}
       />
    <Button size="sm" outline={true} color="secondary" class="ms-2 my-2 my-sm-0 " on:click="{handleClick}">
      {$_("search")}
    </Button>
  </Form>
</Navbar>
