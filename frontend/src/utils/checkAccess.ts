function consecutivePermissionSearch(
  permissions: any,
  space: string,
  resourceType: string
) {
  const scopedPermissionsKeys = [];
  const permissionsKeys = Object.keys(permissions);
  for (const permissionsKey of permissionsKeys) {
    let regex;
    if (permissionsKey.startsWith("__all_spaces__")) {
      regex = new RegExp(`.*:.*:${resourceType}`, "gi");
    } else {
      regex = new RegExp(`${space}:.*:${resourceType}`, "gi");
    }
    const found: any = permissionsKey.match(regex);
    if (found) {
      scopedPermissionsKeys.push(...found);
    }
  }
  return scopedPermissionsKeys;
}

function checkWithMagicWords(key: string, scopedPermissionsKey: string) {
  const scopedPermissionsParts = scopedPermissionsKey.split(":");
  const keyParts = key.split(":");

  if (scopedPermissionsParts.includes("__all_spaces__")) {
    keyParts[0] = "";
  }
  if (scopedPermissionsParts.includes("__all_subpaths__")) {
    keyParts[1] = "";
  }

  const keyToCompare = keyParts.join(":");

  const scopedPermissions = scopedPermissionsParts
    .map((e) => {
      if (["__all_spaces__", "__all_subpaths__"].includes(e)) {
        return "";
      }
      return e;
    })
    .join(":");

  return scopedPermissions === keyToCompare;
}

export default function checkAccess(
  action: string,
  space: string,
  subpath: string,
  resourceType: string
): boolean {
  let permissions = {};
  if (typeof localStorage !== "undefined")
    permissions = JSON.parse(localStorage.getItem("permissions"));

  if (permissions === null || Object.keys(permissions).length === 0) {
    return false;
  }

  const subpaths = subpath.split("/");
  if (subpaths[0] != "/") {
    subpaths.push("/");
  }
  const scopedPermissionsKeys = consecutivePermissionSearch(
    permissions,
    space,
    resourceType
  );

  if (subpath.startsWith("/")) {
    subpath = subpath.slice(1);
  }

  const parts = subpath.split("/");
  const resultArray = [];

  for (let i = parts.length; i > 0; i--) {
    const str = parts.slice(0, i).join("/");
    resultArray.push(str);
    resultArray.push(`${str}/__all_subpaths__`);
  }
  resultArray.push("__all_subpaths__");
  resultArray.push("/");
  for (const _subpath of resultArray) {
    for (const scopedPermissionsKey of scopedPermissionsKeys) {
      const key = `${space}:${_subpath}:${resourceType}`;
      if (checkWithMagicWords(key, scopedPermissionsKey)) {
        if (
          permissions[scopedPermissionsKey] &&
          permissions[scopedPermissionsKey]["allowed_actions"]?.includes(action)
        ) {
          return true;
        }
        break;
      }
    }
  }

  return false;
}

export function checkAccessv2(
  action: string,
  space: string,
  subpath: string,
  resourceType: string
) {
  const keys = [
    `${space}:__all_subpaths__:${resourceType}`,
    `__all_spaces__:__all_subpaths__:${resourceType}`,
    `${space}:${subpath}:${resourceType}`,
  ];

  let permissions = {};
  if (typeof localStorage !== "undefined"){
    permissions = JSON.parse(localStorage.getItem("permissions"));
  }
  if (permissions === null || Object.keys(permissions).length === 0) {
    return false;
  }

  for (const key of keys) {
    if (permissions[key]) {
      return permissions[key].allowed_actions.includes(action);
    }
  }

  return false;
}
