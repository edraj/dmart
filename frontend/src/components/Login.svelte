<script lang="ts">
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
  import { signin } from "@/stores/user";
  import { _ } from "@/i18n";

  let username: string;
  let password: string;

  async function handleSubmit(event: Event) {
    event.preventDefault();

    signin(username, password);
  }
</script>

<Card class="w-25 mx-auto my-auto">
  <CardHeader>{$_("login_to_members")}</CardHeader>
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
