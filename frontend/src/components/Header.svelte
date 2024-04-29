<script lang="ts">
  // import { Form, Input, Button, Navbar, NavbarBrand, Nav, NavLink } from "sveltestrap";
  import {Navbar, NavbarBrand, Nav, NavLink, NavItem, Collapse} from "sveltestrap";
  import { _ } from "@/i18n";
  // import { website } from "@/config";
  // import Icon from "@/components/Icon.svelte";
  // import signedin_user from "../management/_stores/signedin_user";
  import { user, signout } from "@/stores/user";
  // import { redirect } from "@roxi/routify";
  // import LocalizedValue from "./LocalizedValue.svelte";
  import markdownFiles from "@/md_indexer.json";
  import {goto} from "@roxi/routify";

  // let search : string = "";
  // function handleClick(event: Event) {
  //    event.preventDefault();
  // //   $redirect(`/search/posts?q=${encodeURI(search)}`);
  // }

  let term = '';
  let suggestions = [];
  let delayTimer;
  async function handleInputChange(event: any) {
      clearTimeout(delayTimer);
      delayTimer = setTimeout(async function() {
          suggestions = [];
          term = event.target.value;
          if (term===""){
              return;
          }
          const _term = term.toLowerCase();
          for (const file of markdownFiles) {
              try {
                  const _result = file.content.toLowerCase();
                  if (_result.includes(_term)) {
                      suggestions = [
                          ...suggestions,
                          {
                              path: file.path,
                              title: file.filename.replace('.md', '').replace(/-/g, ' ').replace("index", "Home"),
                              description: "..."+_result.substring(
                                  _result.indexOf(_term)-50, _result.indexOf(_term)+50
                              ).replace(_term.toLowerCase(), "<b>"+_term+"</b>")+"..."
                          }
                      ];
                  }
              } catch (e) {
              }
          }
      }, 1000);
  }

  function handleSuggestionClick(suggestion: any) {
      $goto(`/docs/${suggestion.path.replace('.md', '')}`);
      suggestions = [];
  }

  let isOpen = false;
  function handleUpdate(event) {
      isOpen = event.detail.isOpen;
  }
</script>
<Navbar color="light" light expand="md" class="px-2 w-100 py-0" style="border-bottom: solid #cecece">
  <NavbarBrand href="/" title="{$_('home')}">{$_('home')}</NavbarBrand>
  <Collapse {isOpen} navbar expand="md" on:update={handleUpdate}>
  <Nav class="w-100" navbar>
    <NavLink href="/docs" title="{$_('docs')}">{$_('docs')}</NavLink>
    {#if $user && $user.signedin}
      <NavLink class="w-25" href="/management/content">{$user.localized_displayname}</NavLink>
    {/if}
  <div class="w-100 d-flex justify-content-end">
    <div class="position-relative w-50 align-content-center">
      <input type="text" class="form-control" placeholder="Search..."
             bind:value={term}
             on:input={handleInputChange}
             on:focusout={()=>{
              setTimeout(()=>{
                  suggestions = [];
              }, 200);
           }}
             on:focusin={handleInputChange}>
      {#if suggestions.length > 0}
        <ul class="list-group suggestion-list">
          {#each suggestions as suggestion}
            <!-- svelte-ignore a11y-no-noninteractive-element-interactions a11y-click-events-have-key-events -->
            <li class="search-item list-group-item" on:click={() => handleSuggestionClick(suggestion)}>
              <h5>{suggestion.title}</h5>
              {@html suggestion.description}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </div>
    {#if !$user || !$user.signedin}
      <NavLink href="/management/content" title="{$_('login')}">{$_('login')}</NavLink>
    {:else}
      <NavLink href="#" title="{$_('logout')}" on:click="{signout}"> {$_('logout')} </NavLink>
    {/if}
  </Nav>
  </Collapse>
</Navbar>

<style>
    .search-item:hover {
        background-color: #ccc;
    }
    .search-item {
        cursor: pointer;
    }
    .suggestion-list {
        position: absolute;
        z-index: 2;
        width: 100%;
        background-color: white;
        border: 1px solid #ccc;
    }
</style>