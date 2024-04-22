<script lang="ts">
  import {Card, CardHeader, CardFooter, TabContent, TabPane} from "sveltestrap";
  import { createEventDispatcher } from "svelte";
  import { marked } from "marked";
  import { mangle } from "marked-mangle";
  import { gfmHeadingId } from "marked-gfm-heading-id";
    import Icon from "@/components/Icon.svelte";

  const dispatch = createEventDispatcher();
  marked.use(mangle());
  marked.use(gfmHeadingId({
      prefix: "my-prefix-",
  }));

  export let content = "";
  export let handleSave = () => {};

  if (typeof(content) !== "string"){
      content = "";
  }

  let textarea;
  let start = 0, end = 0;
  function handleSelect() {
    start = textarea.selectionStart;
    end = textarea.selectionEnd;
  }

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

<Card fluid={true} class="h-100 pt-1">
  <CardHeader></CardHeader>
    <TabContent>
      <TabPane tabId="editor" tab="Editor" active>
        <textarea
          on:blur={(e)=>{
            e.preventDefault();
            textarea.focus();
          }}
          on:keydown={handleKeyDown}
          bind:this={textarea}
          on:select={handleSelect}
          rows="22"
          maxlength="4096"
          class="h-100 w-100 m-0 font-monospace form-control form-control-sm"
          bind:value={content}
          on:input={() => dispatch("changed")}
        />
      </TabPane>
      <TabPane tabId="preview" tab="Preview">
        <div class="h-100 w-100 p-3" style="overflow: hidden auto">
          {@html marked(content)}
        </div>
      </TabPane>
      <!-- svelte-ignore a11y-no-noninteractive-element-interactions a11y-click-events-have-key-events -->
      <div class="d-flex justify-content-end flex-grow-1">
        <TabPane class="m-0 p-0" onClick={()=>handleFormatting("**")}><p class="text-dark p-0 m-0" slot="tab"><strong>B</strong></p></TabPane>
        <TabPane onClick={()=>handleFormatting("_")}><p class="text-dark p-0 m-0" slot="tab"><i>I</i></p></TabPane>
        <TabPane onClick={()=>handleFormatting("~~")}><p class="text-dark p-0 m-0" slot="tab"><del>S</del></p></TabPane>
        <TabPane onClick={()=>handleFormatting("*", false, true)}><p class="text-dark p-0 m-0" slot="tab">ul</p></TabPane>
        <TabPane onClick={()=>handleFormatting("1.", false, true)}><p class="text-dark p-0 m-0" slot="tab">ol</p></TabPane>
        <TabPane onClick={()=>handleFormatting("#", false)}><p class="text-dark p-0 m-0" slot="tab">H1</p></TabPane>
        <TabPane onClick={()=>handleFormatting("##", false)}><p class="text-dark p-0 m-0" slot="tab">H2</p></TabPane>
        <TabPane onClick={()=>handleFormatting("###", false)}><p class="text-dark p-0 m-0" slot="tab">H3</p></TabPane>
        <TabPane onClick={handleSave}>
          <Icon class="text-success p-0 m-0" name="save" slot="tab"/>
        </TabPane>
      </div>
    </TabContent>
  <CardFooter></CardFooter>
</Card>
