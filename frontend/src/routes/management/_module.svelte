<!-- routify:meta reset -->

<script lang="ts">
    import {Col, Container, Row} from "sveltestrap";
    import {user} from "@/stores/user";
    import Login from "@/components/Login.svelte";
    import Header from "@/components/management/Header.svelte";
    import Sidebar from "@/components/management/Sidebar.svelte";
    import {get_profile, ResourceType, retrieve_entry} from "@/dmart";
    // import { useRegisterSW } from "virtual:pwa-register/svelte";
    import Offline from "@/components/Offline.svelte";
    import TopLoadingBar from "@/components/management/TopLoadingBar.svelte";
    import { fly } from "svelte/transition";
    import { isNetworkError } from "@/stores/management/error_network";
    import { onMount } from "svelte";
    import {metadata} from "@/stores/management/metadata";
    import { goto } from "@roxi/routify";
    $goto

    let props = $props();
    let isOffline = false;

    /*const { offlineReady, needRefresh, updateServiceWorker } = useRegisterSW({
      onRegistered(swr) {
        isOffline = !navigator.onLine;
      },
      onRegisterError(error) {
      },
      onOfflineReady() {
        setTimeout(() => close(), 5000);
      },
    });
    function close() {
      offlineReady.set(false);
      needRefresh.set(false);
    }*/

    let _isNetworkError = $state(false);
    onMount(()=>{
        isNetworkError.subscribe((v)=>{
            _isNetworkError = v;
        });
        (async()=>{
            let data: any = await retrieve_entry(ResourceType.schema,"management","schema","metafile",true,false,true);
            if (data) {
                data = data?.payload?.body ?? {};
                delete data.properties.uuid
                delete data.properties.shortname
                delete data.properties.created_at
                delete data.properties.updated_at
                delete data.properties.is_open
                delete data.properties.workflow_shortname
                delete data.properties.state
                delete data.properties.reporter
                delete data.properties.resolution_reason
                delete data.properties.receiver
                metadata.set(data);
            }
        })();
    });

    let window_height: number = $state(0);
    let header_height: number = $state(0);
</script>

<svelte:window bind:innerHeight={window_height}/>

<TopLoadingBar/>

{#if _isNetworkError}
    <div class="d-flex justify-content-center bg-danger text-white" transition:fly>
        <p class="pt-3 fs-5">Unable to connect to the server.</p>
    </div>
{/if}

{#if isOffline}
    <div class="container-fluid d-flex align-items-start py-3 h-100">
        <Offline/>
    </div>
{:else if !$user || !$user.signedin}
    <div
            class="container-fluid d-flex align-items-start py-3 h-100"
            id="login-container"
    >
        <Login/>
    </div>
{:else}
    <div bind:clientHeight={header_height} class="fixed-top">
        <Header/>
    </div>
    <Container
            fluid={true}
            class="position-relative p-0"
            style="top: {header_height}px; height: {window_height -
      header_height -
      8}px;"
    >
        <Row class="h-100" noGutters>
            {#await get_profile() then _}
                <Col sm="2" class="h-100 border-end border-light px-1">
                    <Sidebar/>
                </Col>
                <Col sm="10" class="h-100 border-end border-light px-1 overflow-auto">
                    <slot />
                </Col>
            {/await}
        </Row>
    </Container>
{/if}
