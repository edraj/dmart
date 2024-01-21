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
  import {REGEX} from "@/utils/regex";

  let username: string;
  let password: string;
  let isError: boolean;
  async function handleSubmit(event: Event) {
    event.preventDefault();
    isError = false;
    try {
      await signin(username, password);
    } catch (error) {
      isError = true;
    }
  }
</script>

<Card class="w-25 mx-auto my-auto">
  <CardHeader>{$_("login_to_members")}</CardHeader>
  <CardBody>
    <Form on:submit={handleSubmit}>
      <FormGroup>
        <Label for="username">{$_("username")}</Label>
        <Input
          class={isError ? "border-danger" : ""}
          type="text"
          name="username"
          bind:value={username}
          required
        />
      </FormGroup>
      <FormGroup>
        <Label for="password">{$_("password")}</Label>
        <Input
          class={isError ? "border-danger" : ""}
          type="password"
          name="password"
          bind:value={password}
          minlength={8}
          maxlength={24}
          pattern={REGEX.PASSWORD}
          required
        />
      </FormGroup>
      {#if isError}
        <p class="text-danger">Wrong credentials!</p>
      {/if}
      <div class="w-100 d-flex align-items-end">
        <Button type="submit" color="primary" class="ms-auto"
          >{$_("login")}</Button
        >
      </div>
    </Form>
  </CardBody>
</Card>
