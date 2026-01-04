<!-- routify:meta reset -->
<script>
    import {goto} from '@roxi/routify';
    import {Dmart} from "@edraj/tsdmart";
    import {website} from "@/config";
    import axios from "axios";
    import Login from "@/components/Login.svelte";
    import ManagementHeader from "@/components/management/ManagementHeader.svelte";
    import {Level} from "@/utils/toast";
    import {debouncedShowToast} from "@/utils/debounce";
    import {Spinner} from "flowbite-svelte";
    import {getSpaces} from "@/lib/dmart_services.js";
    import {onMount} from "svelte";
    import {user} from "@/stores/user.js";

    $goto

    const dmartAxios = axios.create({
        baseURL: website.backend,
        withCredentials: true,
        timeout: website.backend_timeout,
    });
    dmartAxios.interceptors.response.use((request) => {
        return request;
    }, (error) => {
        if(error.code === 'ERR_NETWORK'){
            debouncedShowToast(Level.warn, "Network error.\nPlease check your connection or the server is down.");
        }
        return Promise.reject(error);
    });
    Dmart.setAxiosInstance(dmartAxios);
    getSpaces();
</script>

{#await Dmart.getProfile()}
    <div class="flex w-svw h-svh justify-center items-center">
        <Spinner color="blue" size="16" />
    </div>
{:then _}
    {#if !$user || !$user.signedin}
        <Login />
    {:else}
        <div class="flex flex-col h-screen">
            <ManagementHeader />
            <div class="flex-grow overflow-auto">
                <slot />
            </div>
        </div>
    {/if}
{:catch _}
    <Login />
{/await}
