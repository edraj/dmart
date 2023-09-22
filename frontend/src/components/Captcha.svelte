<script lang="ts">
  import { onMount } from "svelte";
  import { FormGroup, Label, Input } from "sveltestrap";
  import { _, dir } from "@/i18n";

  function randomString(length, chars) {
    var result = "";
    for (var i = length; i > 0; i = i - 1) {
      result += chars[Math.floor(Math.random() * chars.length)];
      // result += ' ';
    }
    return result;
  }

  let canvas_div;
  let image;
  let random;
  onMount(() => {
    random = randomString(4, $_("captcha_chars"));
    //random = randomString(4, "2346789أبتثجحخدذرزسشصضطظعغفقلنو");
    var x = Math.floor(Math.random() * 50);
    if ($dir == "rtl") x += 90;
    var y = Math.floor(Math.random() * 20) + 30;
    if ($dir == "rtl") y -= 5;

    if ("routify" in window /* FIXME && window.routify.inBrowser*/) {
      const ctx = canvas_div.getContext("2d");
      try {
        ctx.strokeRect(1, 1, 149, 59);
        ctx.font = "36px serif";
        //ctx.fillText(random, x, y);
        ctx.strokeText(random, x, y);
        image.src = ctx.canvas.toDataURL();
      } catch (error) {
        console.log("Caught error on captcha canvas ", error);
      }
    }
  });

  export let valid = false;
  let invalid = true;
  function handleInput(event) {
    if (event.target.value.length < 4) {
      // invalid = valid = undefined;
      invalid = true;
      valid = false;
      return;
    }
    if (event.target.value == random) {
      valid = true;
      invalid = false;
    } else {
      invalid = true;
      valid = false;
    }
  }
</script>

<FormGroup row={true} class="mx-1 py-0">
  <canvas bind:this={canvas_div} width="150" height="60" />
  <Label class="col-md-3 text-start px-1 py-0 m-0" for="captcha" size="sm">
    {$_("verfication")}
  </Label>
  <img class="col-md-2" bind:this={image} alt="check me out" />
  <Input
    class="py-0 form-control form-control-sm"
    id="captcha"
    type="text"
    placeholder={$_("enter_code_here")}
    bsSize="lg"
    {invalid}
    {valid}
    on:input={handleInput}
  />
</FormGroup>

<style>
  canvas {
    border: 1px black solid;
    display: none;
    padding: 20px;
  }
</style>
