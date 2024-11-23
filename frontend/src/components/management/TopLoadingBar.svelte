<script module lang="ts">
  import { isSlowNetwork } from "@/stores/management/slow_network";
  import { writable } from "svelte/store";
  export const isLoading = writable(0);
  export const isLoadingIsOkStat = writable(true);
</script>

<script>
  let isVisible = 0;
  let isOk = true;
  let timeId = null;

  isLoading.subscribe((v) => {
    isVisible = v;

    if (isVisible === 0 && timeId !== null) {
      clearTimeout(timeId);
      timeId = null;
      isSlowNetwork.set(false);
    } else if (timeId === null) {
      timeId = setTimeout(() => {
        isSlowNetwork.set(true);
      }, 5000);
    }
  });
  isLoadingIsOkStat.subscribe((v) => {
    isOk = v;
  });
</script>

{#if isVisible}
  <div class="progress-bar-wrapper fixed-top">
    <div class="progress-bar">
      {#key isOk}
        <div
          class={isOk ? "progress-bar-value-ok" : "progress-bar-value-nok"}
        ></div>
      {/key}
    </div>
  </div>
{/if}

<style>
  .progress-bar-wrapper {
    z-index: 1050;
    width: 100%;
    margin: auto;
  }

  .progress-bar {
    height: 4px;
    background-color: rgba(5, 114, 206, 0.2);
    width: 100%;
    overflow: hidden;
  }

  .progress-bar-value-ok {
    width: 100%;
    height: 100%;
    background-color: rgb(5, 114, 206);
    animation: indeterminateAnimation 1s infinite linear;
    transform-origin: 0% 50%;
  }
  .progress-bar-value-nok {
    width: 100%;
    height: 100%;
    background-color: rgb(206, 5, 5);
    animation: indeterminateAnimation 1s infinite linear;
    transform-origin: 0% 50%;
  }

  @keyframes indeterminateAnimation {
    0% {
      transform: translateX(0) scaleX(0);
    }
    40% {
      transform: translateX(0) scaleX(0.4);
    }
    100% {
      transform: translateX(100%) scaleX(0.5);
    }
  }
</style>
