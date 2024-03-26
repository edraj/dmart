<script lang="ts">
  import { search } from "@/stores/management/triggers";
  import {
    Nav,
    NavItem,
    NavLink,
    Navbar,
    Form,
    InputGroup,
    Input,
    InputGroupText,
    Dropdown,
    DropdownItem,
    DropdownMenu,
    DropdownToggle
  } from "sveltestrap";
  import Icon from "../Icon.svelte";
  import { _ } from "@/i18n";
  import SelectLanguage from "../SelectLanguage.svelte";
  import { signout } from "@/stores/user";
  import { url } from "@roxi/routify";
  import { active_section } from "@/stores/management/active_section";
  import sections from "@/stores/management/sections.json";
  import { fly } from "svelte/transition";
  import { isSlowNetwork } from "@/stores/management/slow_network";
  import { onMount } from "svelte";
  import {handleThemeChange, themesList, themesStore} from "@/stores/themes_store";


  let search_value = "";
  function handleSearch(e) {
    e.preventDefault();
    search.set(search_value.replaceAll("@", "."));
  }
  function handleInput(e) {
    search_value = e.target.value;
    if (search_value === "") {
      search.set(search_value);
    }
  }
  let isOnline = navigator.onLine;

  function handleNetStatus() {
    isOnline = navigator.onLine;
  }
  let _isSlowNetwork = false;

  onMount(()=>{
      isSlowNetwork.subscribe((v)=>{
        _isSlowNetwork = v;
      });
  });
</script>

<svelte:window on:online={handleNetStatus} on:offline={handleNetStatus} />

{#if !isOnline}
  <div class="d-flex justify-content-center bg-danger text-white" transition:fly>
    <p class="pt-3 fs-5">Unable to connect due to network issue.</p>
  </div>
  {:else if _isSlowNetwork}
  <div class="d-flex justify-content-center bg-warning" transition:fly>
    <p class="pt-3 fs-5">Slow connectivity detected.</p>
  </div>
{/if}


<Navbar class="py-0 px-0">
  <Nav tabs class="align-items-center w-100" style="background-color: #f4f4f4;">
    {#each sections as section}
        <NavLink
          href={$url("/management/" + section.name)}
          title={$_(section.name)}
          on:click={() => {
            $active_section = section;
          }}
          active={$active_section.name == section.name}
        >
          <Icon name={section.icon} />
          <!--
          {#if section.notifications > 0}
            <span class="badge rounded-pill bg-danger custom-badge">{section.notifications}</span>
          {/if}
          -->
        </NavLink>
    {/each}
      <NavLink href="/" title={$_("published")}>
        <Icon name="globe" />
      </NavLink>
    <NavItem class="ms-auto">
      <Form inline={true} class="ms-auto" on:submit={handleSearch}>
        <InputGroup size="sm">
          <Input
            type="search"
            placeholder={$_("searching_for_what")}
            on:input={handleInput}
          />
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <span on:click={handleSearch}>
            <InputGroupText><Icon name="search" /></InputGroupText>
          </span>
        </InputGroup>
      </Form>
    </NavItem>
    <NavItem>
      <SelectLanguage />
    </NavItem>

      <NavLink href="#" title={$_("logout")} on:click={signout}>
        <Icon name="power" />
      </NavLink>

      <NavItem>
<!--      <Dropdown>-->
<!--        <DropdownToggle><Icon name="palette-fill" /></DropdownToggle>-->
<!--        <DropdownMenu end>-->
<!--          {#each themesList as theme}-->
<!--            <DropdownItem name={theme} on:click={handleThemeChange}>{theme}</DropdownItem>-->
<!--          {/each}-->
<!--        </DropdownMenu>-->
<!--      </Dropdown>-->
    </NavItem>
  </Nav>
</Navbar>

<!--style>
  /*
  .custom-badge {
    position: relative;
    right: 0.5rem;
    top: -0.5rem;
    border: 2px solid #fff;
    font-size: 0.6rem;
  }*/
</style-->
