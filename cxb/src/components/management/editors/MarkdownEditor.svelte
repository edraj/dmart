<script lang="ts">
    import {Button, Card, TabItem, Tabs} from "flowbite-svelte";
    import {createEventDispatcher} from "svelte";
    import {marked} from "marked";
    import {mangle} from "marked-mangle";
    import {gfmHeadingId} from "marked-gfm-heading-id";

    const dispatch = createEventDispatcher();
  marked.use(mangle());
  marked.use(gfmHeadingId({
    prefix: "my-prefix-",
  }));

  let {
    content = $bindable("")
  } : {
    content: string,
    handleSave?: () => void
  } = $props();

  if (typeof(content) !== "string"){
    content = "";
  }

  let textarea;
  let start = 0, end = 0;
  function handleSelect() {
    start = textarea.selectionStart;
    end = textarea.selectionEnd;
  }

  const listViewInsert = "{% ListView \n" +
          "   type=\"subpath\"\n" +
          "   space_name=\"\" \n" +
          "   subpath=\"/\" \n" +
          "   is_clickable=false %}\n" +
          "{% /ListView %}\n";
  const tableInsert = `| Header 1 | Header 2 |
|----------|----------|
|  Cell1   |  Cell2   |`;

  function handleKeyDown(event) {
    if (event.ctrlKey) {
      if (['b','i','t'].includes(event.key)) {
        event.preventDefault();
        switch (event.key) {
          case 'b':
            handleFormatting("**")
            break;
          case 'i':
            handleFormatting("_")
            break;
          case 't':
            handleFormatting("~~")
            break;
        }
      }
    }
  }

  function handleFormatting(format: any, isWrap = true, isPerLine = false){
    if (isWrap && start === 0 && end === 0) {
      return
    }
    if (isWrap) {
      textarea.value = textarea.value.substring(0, start) + format + textarea.value.substring(start, end) + format + textarea.value.substring(end);
    }
    else {
      start = textarea.selectionStart;
      end = textarea.selectionEnd;
      if (isPerLine){
        const lines = textarea.value.split('\n');
        let lineStart = textarea.value.substring(0, start).split('\n').length - 1;
        let lineEnd = textarea.value.substring(0, end).split('\n').length - 1;

        if (textarea.value[end] === '\n') {
          lineEnd--;
        }

        for (let i = lineStart; i <= lineEnd; i++) {
          lines[i] = `${format} ` + lines[i];
        }

        textarea.value = lines.join('\n');
      }
      else {
        let lineStart = textarea.value.lastIndexOf('\n', start - 1) + 1;
        let lineEnd = textarea.value.indexOf('\n', end);
        if (lineEnd === -1) {
          lineEnd = textarea.value.length;
        }
        textarea.value = textarea.value.substring(0, lineStart) + `${format} ` + textarea.value.substring(lineStart, lineEnd) + textarea.value.substring(lineEnd);
      }
    }

    start = 0;
    end = 0;
    content = structuredClone(textarea.value);
  }
</script>

<Card class="h-full max-w-full pt-1">

  <div class="flex flex-wrap justify-end mt-2 pt-2">
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("**")}>
      <strong>B</strong>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("_")}>
      <i>I</i>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("~~")}>
      <del>S</del>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("*", false, true)}>
      <span>ul</span>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("1.", false, true)}>
      <span>li</span>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("#", false)}>
      <span>H1</span>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("##", false)}>
      <span>H2</span>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting("###", false)}>
      <span>H3</span>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting(tableInsert, false)}>
      <span>table</span>
    </Button>
    <Button size="xs" color="light" class="mx-1" onclick={() => handleFormatting(listViewInsert, false)}>
      <span>list view</span>
    </Button>
  </div>

  <Tabs>
    <TabItem open title="Editor">
      <div class="w-full">
        <textarea
            bind:this={textarea}
            onselect={handleSelect}
            onkeydown={handleKeyDown}
            rows="22"
            maxlength="4096"
            class="w-full font-mono bg-white border border-gray-300 rounded-lg p-2.5 focus:ring-blue-500 focus:border-blue-500"
            bind:value={content}
            oninput={() => dispatch("changed")}
            onblur={(e) => {
              e.preventDefault();
              textarea.focus();
            }}
        ></textarea>
      </div>
    </TabItem>
    <TabItem title="Preview">
      <div class="w-full">
        <article class="prose">
          {@html marked(content)}
        </article>
      </div>
    </TabItem>
  </Tabs>
</Card>