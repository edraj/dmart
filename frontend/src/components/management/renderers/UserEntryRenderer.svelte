<script lang="ts">
    import {onDestroy, onMount} from "svelte";
    import {
        check_existing,
        passwordRegExp,
        passwordWrongExp,
        query,
        QueryType,
        request,
        RequestType,
        ResourceType,
        ResponseEntry,
        Status,
    } from "@/dmart";
    import {Button, Form, FormGroup, Input, Label,} from "sveltestrap";
    import {createAjvValidator, Validator,} from "svelte-jsoneditor";
    import {status_line} from "@/stores/management/status_line";
    import {Level, showToast} from "@/utils/toast";
    import "bootstrap";
    import {isDeepEqual, removeEmpty} from "@/utils/compare";
    import metaUserSchema from "@/validations/meta.user.json";
    import {toast} from "@zerodevx/svelte-toast";
    import ToastActionComponent from "@/components/management/ToastActionComponent.svelte";
    import {goto} from "@roxi/routify";
    import {cleanUpSchema} from "@/utils/renderer/rendererUtils";
    import {REGEX} from "@/utils/regex";

    export let entry: ResponseEntry;
  export let space_name: string;
  export let subpath: string;
  export let errorContent: any;

  const resource_type: ResourceType = ResourceType.user;


  let contentMeta: any = { json: {}, text: undefined };
  let validatorMeta: Validator = createAjvValidator({ schema: metaUserSchema });
  let oldContentMeta = { json: entry || {}, text: undefined };

  let contentContent = { json: {}, text: undefined };
  let oldContentContent = { json: {}, text: undefined };
  let validatorContent: Validator = createAjvValidator({ schema: {} });

  onDestroy(() => status_line.set(""));


  let user: any = { displayname: { ar: "", en: "", kd: "" } };

  onMount(async () => {
    user = {
      ...user,
      email: entry?.email,
      msisdn: entry?.msisdn,
      password: "",
      is_email_verified: entry.is_email_verified,
      is_msisdn_verified: entry.is_msisdn_verified,
      force_password_change: entry.force_password_change,
    };
    if (entry.displayname) {
      user.displayname = entry.displayname;
    }

    const cpy = structuredClone(entry);

    if (contentContent === null) {
      contentContent = { json: {}, text: undefined };
    }
    contentContent.json = cpy?.payload?.body ?? {};

    delete cpy?.payload?.body;
    delete cpy?.attachments;
    contentMeta.json = cpy;

    contentContent = structuredClone(contentContent);
    oldContentContent = structuredClone(contentContent);
    contentMeta = structuredClone(contentMeta);
    oldContentMeta = structuredClone(contentMeta);
  });

  let schema = null;
  async function get_schema() {
    if (entry.payload && entry.payload.schema_shortname) {
      const query_schema = {
        space_name,
        type: QueryType.search,
        subpath: "/schema",
        filter_shortnames: [entry.payload.schema_shortname],
        search: "",
        retrieve_json_payload: true,
      };

      const schema_data = await query(query_schema);
      if (schema_data.status == "success" && schema_data.records.length > 0) {
        schema = schema_data.records[0].attributes["payload"].body;
        cleanUpSchema(schema.properties);

        try {
          validatorContent = createAjvValidator({ schema });
        } catch (error) {
          const name = schema_data.records[0].shortname;
          validatorContent = createAjvValidator({ schema: {} });
          toast.push({
            component: {
              src: ToastActionComponent,
              props: {
                level: Level.warn,
                message: `The schema ${name} is corrupted!`,
                action: () => {
                  $goto(
                    "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]",
                    {
                      space_name,
                      subpath: "/schema",
                      shortname: entry.payload.schema_shortname,
                      resource_type: "schema",
                    }
                  );
                },
              },
            },
            initial: 0,
            dismissable: false,
          });
        }
      }
    } else {
      schema = null;
    }
  }

  $: {
    if (
      schema === null &&
      entry &&
      entry.payload &&
      entry.payload.schema_shortname
    ) {
      get_schema();
    }
  }

  onDestroy(() => {
    history.replaceState;
    return false;
  });

  function beforeUnload(event) {
    if (
      !isDeepEqual(removeEmpty(contentMeta), removeEmpty(oldContentMeta)) &&
      !isDeepEqual(removeEmpty(contentContent), removeEmpty(oldContentContent))
    ) {
      event.preventDefault();
      if (
        confirm("You have unsaved changes, do you want to leave ?") === false
      ) {
        return false;
      }
    }
  }

  async function handleUserSubmit(e) {
    e.preventDefault();
    const oldMeta = oldContentMeta.json
        ? structuredClone(oldContentMeta.json)
        : JSON.parse(oldContentMeta.text);

    if (oldMeta.email !==  user.email){
        const emailStatus: any = await check_existing("email", user.email);
        if (!emailStatus.attributes.unique){
            showToast(Level.warn,"Email already exists!");
            return;
        }
    }

    if (oldMeta.msisdn !==  user.msisdn){
        const msisdnStatus: any = await check_existing("msisdn", user.msisdn);
        if (!msisdnStatus.attributes.unique){
            showToast(Level.warn,"MSISDN already exists!");
            return;
        }
    }

    if (user.password === "") {
      delete user.password;
    } else {
      if (!passwordRegExp.test(user.password)){
          showToast(Level.warn, passwordWrongExp);
          return;
      }
    }
    for (const key in user) {
      if (user[key] == null) {
        delete user[key];
      }
    }

    const response = await request({
      space_name: space_name,
      request_type: RequestType.update,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath,
          attributes: user,
        },
      ],
    });
    if (response.status == Status.success) {
      showToast(Level.info);
      window.location.reload();
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  $: user && contentMeta &&
    (() => {
      if (contentMeta.text){
          contentMeta.json = JSON.parse(contentMeta.text);
          contentMeta.text = undefined;
      }
      const meta = structuredClone(contentMeta.json);

      contentMeta.json = { ...meta, ...user };
      meta.displayname = {
        ...meta.displayname,
        ...user.displayname,
      };
      contentMeta.text = undefined;
      contentMeta = structuredClone(contentMeta);
    })()

  $: {
    contentContent = structuredClone(contentContent);
  }
</script>

<svelte:window on:beforeunload={beforeUnload} />

<Form
  class="d-flex flex-column px-5 mt-5 mb-5"
  on:submit={handleUserSubmit}
>
  <div class="row">
    <FormGroup class="col-4">
      <Label>Email</Label>
      <Input
              style="width: 100% !important"
              bind:value={user.email}
              class="w-25"
              type="email"
              name="email"
              placeholder="Email..."
              autocomplete="off"
      />
    </FormGroup>
    <FormGroup class="col-4">
      <Label>MSISDN</Label>
      <Input
              style="width: 100% !important"
              bind:value={user.msisdn}
              class="w-25"
              type="text"
              name="msisdn"
              placeholder="MSISDN..."
              autocomplete="off"
      />
    </FormGroup>
    <FormGroup class="col-4">
      <Label>Password</Label>
      <Input
              style="width: 100% !important"
              bind:value={user.password}
              class="w-25"
              type="password"
              name="password"
              placeholder="password..."
              minlength={8}
              maxlength={24}
              pattern={REGEX.PASSWORD}
              autocomplete="off"
      />
    </FormGroup>
  </div>
  <div class="row">
    <FormGroup class="col-4">
      <Label>English Displayname</Label>
      <Input
              style="width: 100% !important"
              bind:value={user.displayname.en}
              class="w-25"
              type="text"
              name="displayname_en"
              placeholder="English Displayname..."
      />
    </FormGroup>
    <FormGroup class="col-4">
      <Label>Arabic Displayname</Label>
      <Input
              style="width: 100% !important"
              bind:value={user.displayname.ar}
              class="w-25"
              type="text"
              name="displayname_ar"
              placeholder="Arabic Displayname..."
      />
    </FormGroup>
    <FormGroup class="col-4">
      <Label>Kurdish Displayname</Label>
      <Input
              style="width: 100% !important"
              bind:value={user.displayname.kd}
              class="w-25"
              type="text"
              name="displayname_kd"
              placeholder="Kurdish Displayname..."
      />
    </FormGroup>
  </div>
  <div class="row">
    <FormGroup class="col-4">
      <Input
        name="is_email_verified"
        bind:checked={user.is_email_verified}
        type="checkbox"
        label="Is Email Verified"
      />
    </FormGroup>
    <FormGroup class="col-4">
      <Input
        name="is_msisdn_verified"
        bind:checked={user.is_msisdn_verified}
        type="checkbox"
        label="Is MSISDN Verified"
      />
    </FormGroup>
    <FormGroup class="col-4">
      <Input
        name="force_password_change"
        bind:checked={user.force_password_change}
        type="checkbox"
        label="Force Password Change"
      />
    </FormGroup>
  </div>
  <Button color="primary" style="width: 25% !important" type="submit"
  >Save</Button
  >
</Form>
