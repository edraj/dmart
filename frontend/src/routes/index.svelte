<script>
  import { goto } from "@roxi/routify";
  import { user } from "@/stores/user";

  if (!$user || !$user.signedin) {
    $goto("/login");
  } else {
    $goto("/management/content");
  }
</script>
