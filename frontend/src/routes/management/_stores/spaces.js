import { dmartRequest } from "../../../dmart.js";
import signedin_user from "./signedin_user.js";
import { writable } from "svelte/store";

const { subscribe, set } = writable({});

const spaces = {
  set: (value) => set(value),
  subscribe,
  reset: () => customSet([]),
};

/**
 *
 * @param spaceName: str
 * @returns list of subpaths of the given space name
 */
const getSpaceSubpaths = async (spaceName) => {
  const response = await dmartRequest("managed/query", {
    type: "subpath",
    space_name: spaceName,
    subpath: "/",
    retrieve_json_payload: true,
    retrieve_attachments: true,
  });
  if (response.status === "success") {
    response.records.map((record) => {
      if (`/${record.shortname}` !== record.subpath)
        record.subpath += record.shortname;
      return record;
    });
    return response.records;
  } else {
    return null;
  }
};

/**
 * fetch from dmart the spaces.
 * set 'space_managment.spaces' as array (str) of spaces
 */
export const getSpaces = async () => {
  const response = await dmartRequest("managed/query", {
    type: "spaces",
    space_name: "demo",
    subpath: "/",
    retrieve_json_payload: true,
    filter_schema_names: [],
    filter_types: [],
    filter_shortnames: [],
    search: "",
    limit: 100,
    offset: 0,
  });
  if (response.status === "success") {
    const _spaces = await Promise.all(
      response.records.map(async (e) => {
        return {
          type: "folder",
          ...e,
          subpaths: await getSpaceSubpaths(e.shortname),
        };
      })
    );
    spaces.set({
      children: _spaces,
      icon: "house-door",
      name: "dashboard",
    });
    return true;
  } else {
    if (response.error.type === "jwtauth") {
      await signedin_user.logout();
    }
    return false;
  }
};

export default spaces;
