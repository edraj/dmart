<script lang="ts">
  import { get_profile, get_children, ResourceType } from '@/dmart';
  import { ListGroup, ListGroupItem } from 'sveltestrap';
  import Icon from '../../Icon.svelte';
  import {_} from '@/i18n';
  import Folder from "../Folder.svelte";

</script>

{#await get_profile()}
  <h3> Loading profile </h3>
{:then profile_data}
  {#if profile_data.records[0].attributes.displayname}
    <strong>Displayname</strong> {profile_data.records[0].attributes.displayname.en}
    <hr />
  {/if} 
  <strong> Notifications / Inbox </strong>
  <ListGroupItem class="ps-2 pe-0 py-0">
    <!--Folder folder={{subpath:`/people/${profile_data.records[0].shortname}`, resource_type: ResourceType.folder, shortname:'notifications', attributes:{}}} space_name="personal" /-->
    {#await get_children("personal", `/people/${profile_data.records[0].shortname}`, 10, 0, [ResourceType.folder])}
      <!--h4> Loading {space.shortname} </h4-->
    {:then children_data}
      {#each children_data.records as folder}
        <Folder {folder} space_name="personal" />
      {/each}
    {:catch error}
      <p style="color: red">{error.message}</p>
    {/await}
  </ListGroupItem>
    <br/>
    <strong>Roles </strong>
    <ListGroup flush>
      {#each profile_data.records[0].attributes.roles as role}
        <ListGroupItem disabled >{role}</ListGroupItem>
      {/each}
    </ListGroup>
{:catch error}
	<p style="color: red">{error.message}</p>
{/await}
