<script>
  import {
    Card,
    CardHeader,
    CardBody,
    Form,
    FormGroup,
    Label,
    Input,
    Button,
  } from "sveltestrap";
  import signedin_user from "../management/_stores/signedin_user.js";
  import { dmartLogin } from "../../dmart.js";
  import { _ } from "../../i18n/index.js";

  let username;
  let password;

  async function handleSubmit() {
    // TBD KEFAH CHECK
    event.preventDefault();
    let resp = await dmartLogin(username, password);
    let user = resp.records[0];
    if (user.attributes?.displayname?.en) {
      user.displayname = user.attributes.displayname.en;
    } else {
      user.displayname = user.shortname;
    }

    signedin_user.login(user);
  }
</script>

<Card class="w-25 mx-auto my-auto">
  <CardHeader class="text-center">{$_("login_to_members")}</CardHeader>
  <CardBody>
    <Form on:submit={handleSubmit}>
      <FormGroup>
        <Label for="username">{$_("username")}</Label>
        <Input type="text" name="username" bind:value={username} />
      </FormGroup>
      <FormGroup>
        <Label for="password">{$_("password")}</Label>
        <Input type="password" name="password" bind:value={password} />
      </FormGroup>
      <div class="w-100 d-flex align-items-end">
        <Button type="submit" color="primary" class="ms-auto"
          >{$_("login")}</Button
        >
      </div>
    </Form>
  </CardBody>
</Card>
