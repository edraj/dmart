<script lang="ts">
  import { data } from "./data";

  function consecutivePermissionSearch(space, resourceType, permissions) {
    const scopedPermissionsKeys = [];
    const permissionsKeys = Object.keys(permissions);
    for (const permissionsKey of permissionsKeys) {
      const regex = new RegExp(`${space}:.*:${resourceType}`, "gi");
      const found = permissionsKey.match(regex);
      if (found) {
        scopedPermissionsKeys.push(...found);
      }
    }
    return scopedPermissionsKeys;
  }

  function checkAccess(
    space: string,
    subpath: string,
    resourceType: string,
    action: string,
    permissions
  ): boolean {
    const subpaths = subpath.split("/");
    if (subpaths[0] != "/") {
      subpaths.push("/");
    }

    const scopedPermissionsKeys = consecutivePermissionSearch(
      space,
      resourceType,
      permissions
    );

    for (const _subpath of subpaths) {
      for (const scopedPermissionsKey of scopedPermissionsKeys) {
        const key = `${space}:${_subpath}:${resourceType}`;
        if (scopedPermissionsKey.includes(key)) {
          if (
            permissions[key] &&
            permissions[key]["allowed_actions"].includes(action)
          ) {
            return true;
          }
          break;
        }
      }
    }

    return false;
  }
  const permissions = data.records[0].permissions;
  let condition = checkAccess(
    "aftersales",
    "collections",
    "comment",
    "query",
    permissions
  );
  let message: string = "Nice day";
</script>

<p>{message}</p>
<p>{condition}</p>
