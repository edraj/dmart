<script lang="ts">
    import EmptyWorkingarea from "@/components/management/EmptyWorkingarea.svelte";
    import {query, QueryType, ResourceType, retrieve_entry} from "@/dmart";
    import {user} from "@/stores/user";
    import {Badge, Card, CardBody, CardSubtitle, CardText, CardTitle, Col, Row} from "sveltestrap";
    import Icon from "@/components/Icon.svelte";

    let userRecord: any = {};
    (async()=>{
        userRecord = await retrieve_entry(
            ResourceType.user,
            "management",
            "users",
            $user.shortname,
            true,
            false,
            false,
        );
        console.log({userRecord})
    })()
</script>


<Card class="p-3 m-5">
  <CardBody>
    <CardTitle class="mb-5" tag="h5">
      <Row class="justify-content-between">
        <Col>{userRecord.shortname}</Col>
        <Col class="d-flex justify-content-end">{userRecord.uuid}</Col>
      </Row>
    </CardTitle>


    <CardText>
      <Card class="d-flex flex-row justify-content-between px-4 py-3">
        <span>
          <Icon name="person-lines-fill" /> {userRecord.type}
        </span>

        <span>
          <Icon name="envelope-at" /> {userRecord.email}
        </span>

        <span>
          <Icon name="telephone" /> {userRecord.msisdn}
        </span>
      </Card>

      <div class="my-3"><b>Displayname:</b></div>
      <Card class="d-flex flex-row justify-content-between px-4 py-3">
        {#each Object.keys(userRecord.displayname ?? {}) as keyDisplayname}
          <span>
            <b class="text-capitalize">{keyDisplayname}:</b> {userRecord.displayname[keyDisplayname] || "N/A"}
          </span>
        {/each}
      </Card>

      <div class="my-3"><b>Checks:</b></div>
      <Card class="d-flex flex-row justify-content-between px-4 py-3">
        {#each [
            "is_active",
            "force_password_change",
            "is_email_verified",
            "is_msisdn_verified"
        ] as keyCheck}
          <span>
            <b class="text-capitalize">{keyCheck.replaceAll("_", " ")}:</b> {userRecord[keyCheck]}
          </span>
        {/each}
      </Card>

      <div class="my-3"><b>Roles:</b></div>
      <ul class="p-0">
        {#each userRecord.roles || [] as role}
          <Badge class="m-1" color="primary">{role}</Badge>
        {/each}
      </ul>
    </CardText>
  </CardBody>
</Card>
