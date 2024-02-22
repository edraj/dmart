<script lang="ts">
  //import classnames from './utils';

  let className = "";
  export { className as class };
  export let name : string;

  function toClassName(value : any) {
    let result = "";

    if (typeof value === "string" || typeof value === "number") {
      result += value;
    } else if (typeof value === "object") {
      if (Array.isArray(value)) {
        result = value.map(toClassName).filter(Boolean).join(" ");
      } else {
        for (let key in value) {
          if (value[key]) {
            result && (result += " ");
            result += key;
          }
        }
      }
    }

    return result;
  }

  function classnames(...args) {
    return args.map(toClassName).filter(Boolean).join(" ");
  }

  $: classes = classnames(className, `bi-${name} icon`);
</script>

<i {...$$restProps} class="{classes}"></i>
