<script>
  import {
    Form,
    Input,
    Button,
    Navbar,
    NavbarBrand,
    Nav,
    NavLink,
    Dropdown,
    DropdownItem,
    DropdownMenu,
    DropdownToggle,
  } from "sveltestrap";
  import { _, locale } from "../../../i18n/index.js";
  import { website } from "../../../config.js";
  import signedin_user from "../_stores/signedin_user.js";
  // import { redirect } from "@roxi/routify";
  import LocalizedValue from "./LocalizedValue.svelte";
  import Fa from "sveltejs-fontawesome";
  import { faRightFromBracket } from "@fortawesome/free-solid-svg-icons";
  import { triggerSearchList } from "../_stores/trigger_refresh.js";

  let search;
  function handleClick(event) {
    event.preventDefault();
    triggerSearchList.set(search);
  }
  async function handleLogout() {
    await signedin_user.logout();
  }
</script>

<Navbar color="light" light expand="md" class="px-0 w-100 py-0">
  <Nav class="justify-content-start" navbar>
    <NavbarBrand href="/">
      <LocalizedValue field={website.short_name} />
    </NavbarBrand>

    <!-- <NavLink href="/managed/folder/posts"
        >{$signedin_user.displayname}</NavLink
      > -->
    <NavLink href="/management/dashboard">Dashbaord</NavLink>
    <NavLink href="/management/qatool">QA Tool</NavLink>

    <!-- <NavLink href="/about">{$_("about")}</NavLink> -->
    <!-- <NavLink href="/contact">{$_("contact_us")}</NavLink> -->
    {#if !$signedin_user}
      <NavLink href="/management">{$_("login")}</NavLink>
    {/if}
  </Nav>
  <Form inline="true" class="w-50 justify-content-center d-flex my-2 my-lg-0">
    <Input
      bsSize="sm"
      type="search"
      readonly={false}
      placeholder={$_("searching_for_what")}
      class=" ms-sm-2 "
      bind:value={search}
      tag="input"
    />
    <Button
      size="sm"
      outline="true"
      color="secondary"
      class="ms-2 my-2 my-sm-0 "
      on:click={handleClick}
    >
      {$_("search")}
    </Button>
  </Form>
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  {#if $signedin_user}
    <Dropdown class="justify-content-end" style="margin-left: 16px">
      <DropdownToggle caret>{$signedin_user.displayname}</DropdownToggle>
      <DropdownMenu>
        <DropdownItem on:click={async () => await handleLogout()}
          ><div class="d-flex row">
            <div class="col-2">
              <Fa icon={faRightFromBracket} size={"lg"} color={"grey"} />
            </div>
            <div class="col-10">Logout</div>
          </div></DropdownItem
        >
      </DropdownMenu>
    </Dropdown>
  {/if}
</Navbar>
