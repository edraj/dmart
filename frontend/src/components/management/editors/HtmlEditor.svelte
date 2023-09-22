<script>
  import { onMount } from "svelte";
  import Editor from "cl-editor";
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  export let uid = "x";
  export let content;

  let maindiv;
  let editor = null;

  onMount(async () => {
    editor = new Editor({
      target: maindiv,
      props: {
        height: "calc(90%)",
        actions: [
          "viewHtml",
          "undo",
          "redo",
          "b",
          "i",
          //'u',
          //'strike',
          //'sup',
          "sub",
          "h1",
          "h2",
          "p",
          "blockquote",
          "ol",
          "ul",
          "hr",
          "left",
          "right",
          "center",
          "justify",
          "a",
          "image",
          //'forecolor',
          //'backcolor',
          "removeFormat",
          /*{
							name: 'save', // required
							icon: '<svg class="icon blink"><use xlink:href="/symbol-defs.svg#floppy-disk" /></svg>', // string or html string (ex. <svg>...</svg>)
							title: 'Save',
							result: () => {
								if(changed) {
									let html = editor.getHtml(true);
									data.attributes.payload.embedded = html;
									update(html);
									//console.log("Hi there: ", html);
									changed = false;
								}
							}
            }*/
        ],
      },
    });
    editor.setHtml(content, true);
    editor.$on("change", () => {
      content = editor.getHtml(true);
      dispatch("changed");
    });

  });

  $: {
    if (editor && content != editor.getHtml(true)) {
      editor.setHtml(content, true);
    }
  }
</script>

<div class="h-100 pt-1" bind:this="{maindiv}" id="htmleditor-{uid}"></div>

<style>
  :global(.cl) {
    height: 100%;
  }
  :global(.cl-content) {
    font-family: "uthmantn";
    font-size: 1rem !important;
  }
</style>
