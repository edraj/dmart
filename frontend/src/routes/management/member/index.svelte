<script lang="ts">
    import {get_profile, ResourceType, retrieve_entry} from "@/dmart";
    import {user} from "@/stores/user";
    import {Badge, Card, CardBody, CardText, CardTitle, Col, ListGroup, ListGroupItem, Row} from "sveltestrap";
    import Icon from "@/components/Icon.svelte";
    import {Level, showToast} from "@/utils/toast";
    import Prism from "@/components/Prism.svelte";

    let userRecord: any = {};
    (async () => {
        userRecord = await get_profile();
        userRecord = userRecord.records[0];
    })()

    let selectedRole = null;
    let selectedPermission = null;

    const permissionList = {}
    const permissionDetails = {}

    async function handleSelectedRole(role: any) {
        if (selectedRole === role) {
            selectedRole = null;
            return;
        }
        if (permissionList[role] === undefined) {
            try {
                permissionList[role] = await retrieve_entry(
                    ResourceType.role,
                    "management",
                    "roles",
                    role,
                    true,
                    false,
                    true
                );
                permissionList[role] = permissionList[role].permissions
            } catch (e) {
                showToast(Level.warn, "Failed to retrieve that role!\n" + e.message);
                permissionList[role] = null;
            }
        }
        selectedRole = role;
    }

    async function handleSelectedPermission(permission: any) {
        if (selectedPermission === permission) {
            selectedPermission = null;
            return;
        }
        if (permissionList[permission] === undefined) {
            try {
                permissionDetails[permission] = await retrieve_entry(
                    ResourceType.permission,
                    "management",
                    "permissions",
                    permission,
                    true,
                    false,
                    true
                );
            } catch (e) {
                showToast(Level.warn, "Failed to retrieve that permission!");
                permissionDetails[permission] = null;
            }
        }

        selectedPermission = permission;
    }

</script>


<Card class="p-3 m-5">
  <CardBody>
    <CardTitle class="mb-5" tag="h5">
      <Row>
        <Col>{userRecord.shortname}</Col>
      </Row>
    </CardTitle>


    <CardText>
      <Card class="d-flex flex-row justify-content-between px-4 py-3">
        <span>
          <Icon name="person-lines-fill"/> {userRecord?.attributes?.type || "N/A"}
        </span>

        <span>
          <Icon name="envelope-at"/> {userRecord?.attributes?.email || "N/A"}
        </span>

        <span>
          <Icon name="telephone"/> {userRecord?.attributes?.msisdn || "N/A"}
        </span>
      </Card>

      <div class="my-3"><b>Displayname:</b></div>
      <Card class="d-flex flex-row justify-content-between px-4 py-3">
        {#each Object.keys(userRecord?.attributes?.displayname ?? {}) as keyDisplayname}
          <span>
            <b class="text-capitalize">{keyDisplayname}:</b> {userRecord?.attributes?.displayname[keyDisplayname] || "N/A"}
          </span>
        {/each}
      </Card>

      <div class="my-3"><b>Checks:</b></div>
      <Card class="d-flex flex-row justify-content-between px-4 py-3">
        {#each [
            "force_password_change",
            "is_email_verified",
            "is_msisdn_verified"
        ] as keyCheck}
          <span>
            <b class="text-capitalize">{keyCheck.replaceAll("_", " ")}:</b> {userRecord?.attributes?.[keyCheck]}
          </span>
        {/each}
      </Card>

      <div class="my-3"><b>Roles:</b></div>
      <ul class="d-flex p-0">
        {#each userRecord?.attributes?.roles || [] as role}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div onclick="{()=>handleSelectedRole(role)}">
            <Badge class="m-1 p-3" color="{
                permissionList[role] === null ? 'danger' : (selectedRole===role?'primary':'secondary')
              }" style="font-size: 1rem; cursor: pointer">
              {role}
            </Badge>
          </div>
        {/each}
      </ul>

      {#if permissionList[selectedRole]}
        <Card class="d-flex justify-content-between px-4 py-3">
          <CardTitle>
            Roles details
          </CardTitle>
          <CardBody class="flex-row p-0">
            <ul class="d-flex p-0">
              {#each permissionList[selectedRole] || [] as permission}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div onclick="{()=>handleSelectedPermission(permission)}">
                  <Badge class="m-1 p-3" color="{
                    permissionDetails[permission] === null ? 'danger' : (selectedPermission===permission?'primary':'secondary')
                  }" style="font-size: 1rem; cursor: pointer">
                    {permission}
                  </Badge>
                </div>
              {/each}
            </ul>

            {#if permissionDetails[selectedPermission]}
              <Card class="d-flex justify-content-between px-4 py-3">
                <CardTitle>
                  Permission details
                </CardTitle>
                <CardBody class="flex-row p-0">
                  <ListGroup>
                      <ListGroupItem>
                        <b>Subpaths: </b>
                        {#each Object.keys(permissionDetails[selectedPermission].subpaths) as subpath}
                          <ListGroupItem>
                            <b>{subpath}:</b> {permissionDetails[selectedPermission].subpaths[subpath].join(", ")}
                          </ListGroupItem>
                        {/each}
                      </ListGroupItem>
                    <ListGroupItem>
                      <b>resource_types:</b> {permissionDetails[selectedPermission].resource_types.join(", ")}
                    </ListGroupItem>
                    <ListGroupItem>
                      <b>actions:</b> {permissionDetails[selectedPermission].actions.join(", ")}
                    </ListGroupItem>
                    <ListGroupItem>
                      <b>conditions:</b> {permissionDetails[selectedPermission].conditions.join(", ")}
                    </ListGroupItem>
                    <ListGroupItem>
                      <b>restricted_fields:</b> {permissionDetails[selectedPermission].restricted_fields.join(", ")}
                    </ListGroupItem>
                  </ListGroup>
                </CardBody>
              </Card>
            {/if}
          </CardBody>
        </Card>
      {/if}


      {#if userRecord?.payload?.body}
        <div class="my-3"><b>Payload body:</b></div>
        <CardBody>
          <Prism code={userRecord?.payload?.body}/>
        </CardBody>
      {/if}
    </CardText>
  </CardBody>
</Card>
