<script lang="ts">
    import {onDestroy, onMount} from "svelte";
    import {
        check_existing_user,
        passwordRegExp,
        passwordWrongExp,
        request,
        RequestType,
        ResourceType,
        type ResponseEntry,
        retrieve_entry,
        Status,
    } from "@/dmart";
    import {Button, Form, FormGroup, Input, Label,} from "sveltestrap";
    import {createAjvValidator, type Validator,} from "svelte-jsoneditor";
    import {status_line} from "@/stores/management/status_line";
    import {Level, showToast} from "@/utils/toast";
    import "bootstrap";
    import {isDeepEqual, removeEmpty} from "@/utils/compare";
    import metaUserSchema from "@/validations/meta.user.json";
    import {toast} from "@zerodevx/svelte-toast";
    import ToastActionComponent from "@/components/management/ToastActionComponent.svelte";
    import {goto} from "@roxi/routify";
    $goto
    import {cleanUpSchema} from "@/utils/renderer/rendererUtils";
    import {REGEX} from "@/utils/regex";

    let {
        entry = $bindable(),
        space_name,
        subpath,
        errorContent = $bindable(),
    } : {
        entry: ResponseEntry,
        space_name: string,
        subpath: string,
        errorContent: any | ResponseEntry,
    } = $props();

    const resource_type: ResourceType = ResourceType.user;

    let contentMeta: any = {json: {}, text: undefined};
    let validatorMeta: Validator = createAjvValidator({schema: metaUserSchema});
    let oldContentMeta = {json: entry || {}, text: undefined};

    let contentContent = {json: {}, text: undefined};
    let oldContentContent = {json: {}, text: undefined};
    let validatorContent: Validator = createAjvValidator({schema: {}});

    onDestroy(() => status_line.set(""));


    let user: any = $state({displayname: {ar: "", en: "", kd: ""}});

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

        const cpy = {...entry};

        if (contentContent === null) {
            contentContent = {json: {}, text: undefined};
        }
        contentContent.json = cpy?.payload?.body ?? {};

        delete cpy?.payload?.body;
        delete cpy?.attachments;
        contentMeta.json = cpy;

        contentContent = {...contentContent};
        oldContentContent = {...contentContent};
        contentMeta = {...contentMeta};
        oldContentMeta = {...contentMeta};
    });

    let schema = null;

    async function get_schema() {
        if (entry.payload && entry.payload.schema_shortname) {
            try {
                const schema_data = await retrieve_entry(
                    ResourceType.schema,
                    space_name,
                    "/schema",
                    entry.payload.schema_shortname,
                    true,
                    false,
                    true,
                );
                const schema = schema_data.payload.body;
                cleanUpSchema(schema);
                validatorContent = createAjvValidator({schema});
            } catch (error) {
                validatorContent = createAjvValidator({schema: {}});
                toast.push({
                    component: {
                        src: ToastActionComponent,
                        props: {
                            level: Level.warn,
                            message: `The schema ${entry.payload.schema_shortname} is corrupted!`,
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
    }

    $effect(() => {
        if (
            schema === null &&
            entry &&
            entry.payload &&
            entry.payload.schema_shortname
        ) {
            get_schema();
        }
    });

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
            ? {...oldContentMeta.json}
            : JSON.parse(oldContentMeta.text);

        if (oldMeta.email !== user.email) {
            const emailStatus: any = await check_existing_user("email", user.email);
            if (!emailStatus.attributes.unique) {
                showToast(Level.warn, "Email already exists!");
                return;
            }
        }

        if (oldMeta.msisdn !== user.msisdn) {
            const msisdnStatus: any = await check_existing_user("msisdn", user.msisdn);
            if (!msisdnStatus.attributes.unique) {
                showToast(Level.warn, "MSISDN already exists!");
                return;
            }
        }

        if (user.password === "") {
            delete user.password;
        } else {
            if (!passwordRegExp.test(user.password)) {
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

    $effect(() => user && contentMeta &&
    (() => {
        if (contentMeta.text) {
            contentMeta.json = JSON.parse(contentMeta.text);
            contentMeta.text = undefined;
        }
        const meta = {...contentMeta.json};

        contentMeta.json = {...meta, ...user};
        meta.displayname = {
            ...meta.displayname,
            ...user.displayname,
        };
        contentMeta.text = undefined;
        contentMeta = {...contentMeta.json};
    })());

    $effect(() => {
        contentContent = {...contentContent};
    });
</script>

<svelte:window on:beforeunload={beforeUnload}/>

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
  <Button color="primary" style="width: 25% !important" type="submit">Save</Button>
</Form>
