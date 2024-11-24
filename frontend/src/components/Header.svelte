<script lang="ts">
  import {
      Navbar,
      NavbarBrand,
      Nav,
      NavLink,
      Collapse,
      Dropdown,
      DropdownToggle,
      DropdownMenu,
      DropdownItem
  } from "sveltestrap";
  import { _ } from "@/i18n";
  import { user, signout } from "@/stores/user";
  import markdownFiles from "@/md_indexer.json";
  import {goto} from "@roxi/routify";
  $goto

  let term = $state('');
  let suggestions = $state([]);
  let delayTimer = $state(null);

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

  let isOpen = $state(false);
</script>
<Navbar color="light" light expand="md"
        class="px-2 w-100 py-0"
        style="border-bottom: solid #cecece">
  <NavbarBrand href="/" title={$_('home')}>{$_('home')}</NavbarBrand>
  <Collapse {isOpen} navbar expand="md">
  <Nav class="w-100 align-items-center" navbar>
    <NavLink href="/docs" title={$_('docs')}>{$_('docs')}</NavLink>
    <div class="w-100 d-flex justify-content-end">
      <div class="position-relative w-50 align-content-center">
      <input type="text" class="form-control" placeholder="Search..."
       bind:value={term}
       oninput={handleInputChange}
       onfocusout={()=>{
        setTimeout(()=>{
            suggestions = [];
        }, 200);
     }}
       onfocusin={handleInputChange}>
      {#if suggestions.length > 0}
        <ul class="list-group suggestion-list">
          {#each suggestions as suggestion}

            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            <!-- svelte-ignore a11y_click_events_have_key_events -->

            <li class="search-item list-group-item" onclick={() => handleSuggestionClick(suggestion)}>
              <h5>{suggestion.title}</h5>
              {@html suggestion.description}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
    </div>
    {#if $user?.signedin}
      <NavLink href="/management/content"></NavLink>
      <Dropdown>
        <DropdownToggle caret>{$user.localized_displayname}</DropdownToggle>
        <DropdownMenu end>
          <DropdownItem href="/management/content" title={$_('login')}>
            {$_('dashboard')}
          </DropdownItem>
          <DropdownItem title={$_('logout')} onclick={signout}>
            {$_('logout')}
          </DropdownItem>
        </DropdownMenu>
      </Dropdown>
    {:else}
      <NavLink href="/management/content" title={$_('login')}>{$_('login')}</NavLink>
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
